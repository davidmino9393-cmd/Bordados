"""El almacén de datos cumple las mismas reglas sobre SQLite y sobre PostgreSQL.

PostgreSQL se prueba contra una base real: `EMBROIDERY_TEST_DATABASE_URL` o, si no está, la de desarrollo en
`services/api/.runtime/postgres-dev.json`. Cada prueba usa un esquema propio que se borra al terminar.
Sin ninguna de las dos, las pruebas de PostgreSQL se omiten.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import urllib.parse
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "packages" / "contracts"))
sys.path.insert(0, str(ROOT / "workers" / "embroidery"))

from embroidery_api.errors import ApiProblem
from embroidery_api.store import Store, canonical

try:
    import psycopg
    from embroidery_api.store_postgres import PostgresStore
except ImportError:  # sin psycopg solo se prueba SQLite
    psycopg = PostgresStore = None

DEV_URL_FILE = ROOT / "services" / "api" / ".runtime" / "postgres-dev.json"


def postgres_test_url():
    if psycopg is None:
        return None
    url = os.environ.get("EMBROIDERY_TEST_DATABASE_URL")
    if url:
        return url
    if DEV_URL_FILE.exists():
        return json.loads(DEV_URL_FILE.read_text(encoding="utf-8")).get("database_url")
    return None


def isolated_schema_url(case, base_url):
    """Crea un esquema propio, lo borra al terminar la prueba y devuelve la URL que trabaja solo dentro de él."""
    schema = "test_" + uuid.uuid4().hex[:12]
    with psycopg.connect(base_url, autocommit=True) as admin:
        admin.execute(f'CREATE SCHEMA "{schema}"')

    def drop():
        with psycopg.connect(base_url, autocommit=True) as admin:
            admin.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')

    case.addCleanup(drop)
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}options={urllib.parse.quote('-c search_path=' + schema)}"


class StoreContract:
    """Las reglas que la API necesita del almacén, sin importar cuál sea."""

    def open(self):
        raise NotImplementedError

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.prepare()
        self.store = self.open()
        self.addCleanup(self.store.close)

    def prepare(self):
        pass

    def test_a_resource_is_read_back_exactly_and_only_for_its_owner(self):
        body, private = {"nombre": "Anillo ñandú ✓", "medidas": [20.0, 19.8], "anidado": {"ok": True, "nada": None}}, {"ruta": "C:/x/y"}
        self.store.create("project", "p1", "ana", None, body, private)
        found = self.store.get("project", "p1", "ana")
        self.assertEqual((found["body"], found["private"], found["owner"], found["project_id"]), (body, private, "ana", None))
        for owner, identifier in (("otra", "p1"), ("ana", "no-existe")):
            with self.assertRaises(ApiProblem) as caught:
                self.store.get("project", identifier, owner)
            self.assertEqual(caught.exception.code, "NOT_FOUND")

    def test_rows_come_in_creation_order_and_filter_by_kind_owner_and_project(self):
        for index, (owner, project) in enumerate((("ana", "p1"), ("beto", "p1"), ("ana", "p2"), ("ana", "p1"))):
            self.store.create("job", f"j{index}", owner, project, {"n": index})
        self.store.create("asset", "a0", "ana", "p1", {"n": 99})
        ids = lambda **filters: [row["id"] for row in self.store.rows("job", **filters)]  # noqa: E731
        self.assertEqual(ids(), ["j0", "j1", "j2", "j3"])
        self.assertEqual(ids(owner="ana"), ["j0", "j2", "j3"])
        self.assertEqual(ids(owner="ana", project_id="p1"), ["j0", "j3"])
        self.assertEqual([row["id"] for row in self.store.rows("asset")], ["a0"])

    def test_update_replaces_the_body_and_keeps_the_private_data_unless_given(self):
        self.store.create("job", "j", "ana", "p", {"estado": "queued"}, {"ruta": "a"})
        self.store.update("job", "j", {"estado": "running"})
        self.assertEqual(self.store.get("job", "j")["private"], {"ruta": "a"})
        self.store.update("job", "j", {"estado": "done"}, {"ruta": "b"})
        found = self.store.get("job", "j")
        self.assertEqual((found["body"], found["private"]), ({"estado": "done"}, {"ruta": "b"}))

    def test_the_same_kind_and_id_cannot_be_created_twice(self):
        self.store.create("project", "p", "ana", None, {"v": 1})
        with self.assertRaises(Exception):
            self.store.create("project", "p", "ana", None, {"v": 2})
        self.assertEqual(self.store.get("project", "p")["body"], {"v": 1})
        self.store.create("asset", "p", "ana", None, {"v": 3})  # otro tipo con el mismo id sí

    def test_a_transaction_that_fails_leaves_nothing_behind(self):
        with self.assertRaises(RuntimeError):
            with self.store.transaction():
                self.store.create("project", "p", "ana", None, {})
                raise RuntimeError("se corta a la mitad")
        self.assertEqual(self.store.rows("project"), [])
        with self.store.transaction():
            self.store.create("project", "q", "ana", None, {})
        self.assertEqual([row["id"] for row in self.store.rows("project")], ["q"])

    def test_idempotent_replays_the_saved_answer_and_refuses_another_content(self):
        calls = []

        def action():
            calls.append(1)
            self.store.create("project", f"p{len(calls)}", "ana", None, {})
            return 201, {"project_id": f"p{len(calls)}", "texto": "ñandú"}

        first = self.store.idempotent("crear", "clave-1", {"nombre": "A"}, action)
        again = self.store.idempotent("crear", "clave-1", {"nombre": "A"}, action)
        self.assertEqual((first, again, len(calls)), ((201, {"project_id": "p1", "texto": "ñandú"}),) * 2 + (1,))
        with self.assertRaises(ApiProblem) as caught:
            self.store.idempotent("crear", "clave-1", {"nombre": "B"}, action)
        self.assertEqual(caught.exception.code, "IDEMPOTENCY_CONFLICT")
        self.store.idempotent("otro-alcance", "clave-1", {"nombre": "B"}, action)  # la clave vale por alcance
        self.assertEqual(len(calls), 2)
        for key in ("", "x" * 129):
            with self.assertRaises(ApiProblem) as caught:
                self.store.idempotent("crear", key, {}, action)
            self.assertEqual(caught.exception.code, "INVALID_REQUEST")

    def test_an_idempotent_action_that_fails_saves_neither_the_answer_nor_what_it_wrote(self):
        def failing():
            self.store.create("project", "huerfano", "ana", None, {})
            raise RuntimeError("falla")

        with self.assertRaises(RuntimeError):
            self.store.idempotent("crear", "k", {"a": 1}, failing)
        self.assertEqual(self.store.rows("project"), [])
        self.assertEqual(self.store.idempotent("crear", "k", {"a": 1}, lambda: (201, {"ok": True})), (201, {"ok": True}))

    def test_mutate_changes_what_is_saved_now_and_writes_nothing_when_it_declines_or_fails(self):
        self.store.create("job", "j", "ana", "p", {"n": 1}, {"nota": "x"})
        self.store.mutate("job", "j", lambda body, private: ({"n": body["n"] + 1}, None))
        self.assertEqual(self.store.get("job", "j")["body"], {"n": 2})
        self.store.mutate("job", "j", lambda body, private: None)
        with self.assertRaises(RuntimeError):
            self.store.mutate("job", "j", lambda body, private: (_ for _ in ()).throw(RuntimeError("no escribas")))
        found = self.store.get("job", "j")
        self.assertEqual((found["body"], found["private"]), ({"n": 2}, {"nota": "x"}))
        with self.store.transaction():  # dentro de otra transacción se une a ella
            self.store.mutate("job", "j", lambda body, private: ({"n": 10}, None))
            self.store.create("project", "p", "ana", None, {})
        self.assertEqual(self.store.get("job", "j")["body"], {"n": 10})

    def test_concurrent_mutations_never_lose_an_update(self):
        self.store.create("contador", "c", "ana", None, {"n": 0})

        def count():
            for _ in range(25):
                self.store.mutate("contador", "c", lambda body, private: ({"n": body["n"] + 1}, None))

        threads = [threading.Thread(target=count) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(60)
        self.assertEqual(self.store.get("contador", "c")["body"], {"n": 100})

    def test_what_was_written_is_still_there_after_closing_and_reopening(self):
        self.store.create("project", "p", "ana", None, {"nombre": "Varios SVG"}, {"ruta": "r"})
        self.store.idempotent("crear", "k", {"a": 1}, lambda: (201, {"project_id": "p"}))
        self.store.close()
        self.store = self.open()
        self.addCleanup(self.store.close)
        self.assertEqual(self.store.get("project", "p", "ana")["body"], {"nombre": "Varios SVG"})
        self.assertEqual(self.store.idempotent("crear", "k", {"a": 1}, lambda: self.fail("no debe repetirse")), (201, {"project_id": "p"}))

    def test_a_large_body_is_stored_as_the_exact_canonical_text(self):
        body = {"texto": "ñandú ✓ " * 100_000, "orden": {"b": 1, "a": 2}}
        self.store.create("job", "grande", "ana", "p", body)
        self.assertEqual(self.store.get("job", "grande")["body"], body)
        self.assertEqual(self.raw_body("job", "grande"), canonical(body))

    def raw_body(self, kind, identifier):
        raise NotImplementedError


class SqliteStoreTests(StoreContract, unittest.TestCase):
    def open(self):
        return Store(self.root)

    def raw_body(self, kind, identifier):
        return self.store.db.execute("SELECT body FROM resources WHERE kind=? AND id=?", (kind, identifier)).fetchone()["body"]


@unittest.skipUnless(postgres_test_url(), "No hay PostgreSQL de prueba (EMBROIDERY_TEST_DATABASE_URL o postgres-dev.json)")
class PostgresStoreTests(StoreContract, unittest.TestCase):
    def prepare(self):
        self.url = isolated_schema_url(self, postgres_test_url())

    def open(self):
        return PostgresStore(self.root, self.url)

    def raw_body(self, kind, identifier):
        return self.store.db.execute("SELECT body FROM resources WHERE kind=? AND id=?", (kind, identifier)).fetchone()["body"]

    def kill_connection(self):
        pid = self.store.db._conn.info.backend_pid
        with psycopg.connect(postgres_test_url(), autocommit=True) as admin:
            admin.execute("SELECT pg_terminate_backend(%s)", (pid,))

    def test_it_reconnects_once_when_the_server_dropped_the_connection_between_requests(self):
        self.store.create("project", "p", "ana", None, {"v": 1})
        self.kill_connection()
        self.assertEqual(self.store.get("project", "p")["body"], {"v": 1})  # sigue funcionando sin reiniciar la API
        self.store.create("project", "q", "ana", None, {"v": 2})
        self.assertEqual([row["id"] for row in self.store.rows("project")], ["p", "q"])

    def test_a_connection_cut_inside_a_transaction_loses_it_and_never_commits_half_of_it(self):
        self.store.create("project", "p", "ana", None, {"v": 1})
        with self.assertRaises(psycopg.Error):
            with self.store.transaction():
                self.store.create("project", "perdido", "ana", None, {})
                self.kill_connection()
                self.store.create("project", "tampoco", "ana", None, {})
        self.assertEqual([row["id"] for row in self.store.rows("project")], ["p"])
        self.store.create("project", "q", "ana", None, {})  # y el almacén queda usable
        self.assertEqual([row["id"] for row in self.store.rows("project")], ["p", "q"])

    def test_the_sequence_keeps_counting_after_the_rows_that_are_already_there(self):
        for index in range(3):
            self.store.create("job", f"j{index}", "ana", "p", {})
        first = [row["sequence"] for row in self.store.rows("job")]
        self.store.create("job", "j3", "ana", "p", {})
        self.assertGreater(self.store.rows("job")[-1]["sequence"], first[-1])


if __name__ == "__main__":
    unittest.main()
