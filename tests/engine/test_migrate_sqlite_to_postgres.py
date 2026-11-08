"""La migración de SQLite a PostgreSQL copia todo, en orden y sin tocar el origen; y se niega a mezclar."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "packages" / "contracts"))
sys.path.insert(0, str(ROOT / "workers" / "embroidery"))

from test_store_backends import isolated_schema_url, postgres_test_url  # noqa: E402

from embroidery_api.store import Store  # noqa: E402
from migrate_sqlite_to_postgres import MigrationRefused, migrate  # noqa: E402

try:
    import psycopg
    from embroidery_api.store_postgres import PostgresConnection, PostgresStore
except ImportError:
    psycopg = None


@unittest.skipUnless(postgres_test_url(), "No hay PostgreSQL de prueba (EMBROIDERY_TEST_DATABASE_URL o postgres-dev.json)")
class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.sqlite = Store(self.root)
        self.addCleanup(self.sqlite.close)
        self.sqlite.create("project", "p1", "ana", None, {"nombre": "Varios SVG ñandú", "n": 1.0}, {})
        self.sqlite.create("asset", "a1", "ana", "p1", {"sha256": "ab" * 32}, {"path": "C:/datos/assets/a1.svg"})
        self.sqlite.create("revision", "r1", "ana", "p1", {"kind": "initial"}, {"settings": {"target": {"width_mm": 130.0}}})
        self.sqlite.create("job", "j1", "ana", "p1", {"status": "needs_review"}, {"job_dir": "C:/datos/jobs/j1"})
        self.sqlite.create("sewout", "s1", "ana", "p1", {"nota": "ok"})
        self.sqlite.create("project", "p2", "beto", None, {"nombre": "Otro"}, {})
        self.sqlite.idempotent("crear", "k1", {"nombre": "Varios"}, lambda: (201, {"project_id": "p1"}))
        self.url = isolated_schema_url(self, postgres_test_url())
        self.file = self.root / "metadata.sqlite3"

    def target(self):
        store = PostgresStore(self.root, self.url)
        self.addCleanup(store.close)
        return store

    def test_everything_is_copied_in_order_with_the_same_content_and_the_source_is_untouched(self):
        before = self.file.read_bytes()
        result = migrate(self.file, self.url)
        self.assertTrue(result["copiado"])
        self.assertEqual(result["recursos"], {"asset": 1, "job": 1, "project": 2, "revision": 1, "sewout": 1})
        self.assertEqual(result["claves_de_idempotencia"], 1)
        target = self.target()
        for kind in ("project", "asset", "revision", "job", "sewout"):
            self.assertEqual(target.rows(kind), self.sqlite.rows(kind), kind)  # mismas filas, mismo orden, mismas secuencias
        self.assertEqual(target.idempotent("crear", "k1", {"nombre": "Varios"}, lambda: self.fail("no debe repetirse")),
                         (201, {"project_id": "p1"}))
        self.assertEqual(self.sqlite.get("project", "p1")["body"], {"nombre": "Varios SVG ñandú", "n": 1.0})
        self.assertEqual(self.file.read_bytes()[:16], before[:16])  # el origen se abrió solo para leer

    def test_the_sequence_goes_on_after_the_copied_rows(self):
        migrate(self.file, self.url)
        target = self.target()
        last = max(row["sequence"] for kind in ("project", "asset", "job") for row in target.rows(kind))
        target.create("job", "j2", "ana", "p1", {})
        self.assertGreater(target.get("job", "j2")["sequence"], last)

    def test_it_refuses_a_destination_that_already_has_data_and_changes_nothing(self):
        migrate(self.file, self.url)
        with self.assertRaises(MigrationRefused):
            migrate(self.file, self.url)
        self.assertEqual(len(self.target().rows("project")), 2)

    def test_a_failure_halfway_leaves_the_destination_empty(self):
        with patch.object(PostgresConnection, "executemany", side_effect=[None, RuntimeError("se corta")]):
            with self.assertRaises(RuntimeError):
                migrate(self.file, self.url)
        target = self.target()
        self.assertEqual((target.rows("project"), target.rows("asset")), ([], []))
        self.assertTrue(migrate(self.file, self.url)["copiado"])  # y se puede reintentar

    def test_a_dry_run_counts_without_touching_postgresql(self):
        result = migrate(self.file, self.url, dry_run=True)
        self.assertEqual((result["copiado"], result["recursos"]["project"]), (False, 2))
        with psycopg.connect(self.url, autocommit=True) as db:
            tables = db.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = current_schema()").fetchone()[0]
        self.assertEqual(tables, 0)


if __name__ == "__main__":
    unittest.main()
