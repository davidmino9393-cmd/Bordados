"""Pasa los datos de una API con SQLite a PostgreSQL: proyectos, archivos, revisiones, trabajos, muestras y claves de idempotencia.

Solo copia filas; no mueve archivos. Los originales, JEF y vistas previas siguen en `data_root` y las rutas guardadas
siguen valiendo mientras esa carpeta no cambie de lugar. El SQLite de origen se abre en solo lectura y no se modifica.
Se niega a escribir en una base de destino que ya tiene datos. Todo ocurre en una sola transacción: o pasa todo o nada.

Uso (desde la raíz del repo, con el entorno de la API):
    python services/api/migrate_sqlite_to_postgres.py --config services/api/.runtime/api-config.json --dry-run
    python services/api/migrate_sqlite_to_postgres.py --config services/api/.runtime/api-config.json
`--config` es la configuración privada de la API: de ahí salen `data_root` y `database_url` (la clave no se muestra).
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from embroidery_api.store import canonical  # noqa: E402

RESOURCE_COLUMNS = "sequence, kind, id, owner, project_id, body, private"
IDEMPOTENCY_COLUMNS = "scope, key, fingerprint, status, body"


class MigrationRefused(Exception):
    """El destino ya tiene datos: no se mezcla ni se pisa nada."""


def _digest(resources, idempotency):
    """Huella del contenido, en orden: si es igual en origen y destino, se copió todo y tal cual."""
    digest = hashlib.sha256()
    for row in resources:
        digest.update(canonical([row[column] for column in RESOURCE_COLUMNS.split(", ")]).encode())
    for row in sorted(idempotency, key=lambda item: (item["scope"], item["key"])):
        digest.update(canonical([row[column] for column in IDEMPOTENCY_COLUMNS.split(", ")]).encode())
    return digest.hexdigest()


def _rewrite_paths(value, old, new):
    """Cambia el prefijo `old` por `new` en toda ruta guardada, conservando el estilo de barras de cada ruta."""
    if isinstance(value, dict):
        return {key: _rewrite_paths(item, old, new) for key, item in value.items()}
    if isinstance(value, list):
        return [_rewrite_paths(item, old, new) for item in value]
    if isinstance(value, str):
        normalized, prefix = value.replace("\\", "/"), old.replace("\\", "/").rstrip("/")
        if normalized.lower() == prefix.lower() or normalized.lower().startswith(prefix.lower() + "/"):
            result = new.replace("\\", "/").rstrip("/") + normalized[len(prefix):]
            return result.replace("/", "\\") if "\\" in value else result
    return value


def migrate(sqlite_file, database_url, dry_run=False, rewrite_root=None):
    source = sqlite3.connect(f"file:{Path(sqlite_file).resolve().as_posix()}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    try:
        resources = [dict(row) for row in source.execute(f"SELECT {RESOURCE_COLUMNS} FROM resources ORDER BY sequence")]
        idempotency = [dict(row) for row in source.execute(f"SELECT {IDEMPOTENCY_COLUMNS} FROM idempotency")]
    finally:
        source.close()
    if rewrite_root:  # los archivos se movieron: las rutas guardadas en `private` apuntan a la carpeta nueva
        old, new = rewrite_root
        for row in resources:
            row["private"] = canonical(_rewrite_paths(json.loads(row["private"]), old, new))
    summary = {
        "recursos": dict(sorted(Counter(row["kind"] for row in resources).items())),
        "claves_de_idempotencia": len(idempotency),
        "huella_del_origen": _digest(resources, idempotency),
        "copiado": False,
    }
    if dry_run:
        return summary

    from embroidery_api.store_postgres import PostgresConnection  # recién acá: el modo de prueba no necesita psycopg

    target = PostgresConnection(database_url)
    try:
        target.initialize()
        existing = target.execute("SELECT (SELECT COUNT(*) FROM resources) AS resources, (SELECT COUNT(*) FROM idempotency) AS keys").fetchone()
        if existing["resources"] or existing["keys"]:
            raise MigrationRefused(f"La base de destino ya tiene datos ({existing['resources']} recursos, {existing['keys']} claves).")
        target.execute("BEGIN IMMEDIATE")
        try:
            target.executemany(
                f"INSERT INTO resources({RESOURCE_COLUMNS}) VALUES(?,?,?,?,?,?,?)",
                [tuple(row[column] for column in RESOURCE_COLUMNS.split(", ")) for row in resources],
            )
            target.executemany(
                f"INSERT INTO idempotency({IDEMPOTENCY_COLUMNS}) VALUES(?,?,?,?,?)",
                [tuple(row[column] for column in IDEMPOTENCY_COLUMNS.split(", ")) for row in idempotency],
            )
            # La secuencia sigue contando después de lo copiado, sin repetir ningún número.
            target.execute("SELECT setval(pg_get_serial_sequence('resources', 'sequence'), "
                           "COALESCE((SELECT MAX(sequence) FROM resources), 1), (SELECT COUNT(*) FROM resources) > 0)")
            copied_resources = [dict(row) for row in target.execute(f"SELECT {RESOURCE_COLUMNS} FROM resources ORDER BY sequence").fetchall()]
            copied_idempotency = [dict(row) for row in target.execute(f"SELECT {IDEMPOTENCY_COLUMNS} FROM idempotency").fetchall()]
            if _digest(copied_resources, copied_idempotency) != summary["huella_del_origen"]:
                raise RuntimeError("Lo copiado no coincide con el origen: no se confirma nada.")
            target.execute("COMMIT")
        except BaseException:
            target.execute("ROLLBACK")
            raise
    finally:
        target.close()
    return {**summary, "copiado": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", type=Path, help="configuración privada de la API (data_root y database_url)")
    parser.add_argument("--sqlite", type=Path, help="metadata.sqlite3 de origen (si no, data_root/metadata.sqlite3 de --config)")
    parser.add_argument("--database-url-file", type=Path, help="JSON con la clave database_url (si no, la de --config)")
    parser.add_argument("--rewrite-root", nargs=2, metavar=("VIEJA", "NUEVA"), help="carpeta de datos de antes y de ahora: corrige las rutas de archivos guardadas")
    parser.add_argument("--dry-run", action="store_true", help="solo cuenta lo que se copiaría; no toca PostgreSQL")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8")) if args.config else {}
    sqlite_file = args.sqlite or (Path(config["data_root"]) / "metadata.sqlite3" if config.get("data_root") else None)
    url_source = json.loads(args.database_url_file.read_text(encoding="utf-8")) if args.database_url_file else config
    if sqlite_file is None or (not args.dry_run and not url_source.get("database_url")):
        parser.error("Faltan el SQLite de origen y la database_url de destino (usá --config o --sqlite y --database-url-file).")
    try:
        result = migrate(sqlite_file, url_source.get("database_url"), args.dry_run, args.rewrite_root)
    except MigrationRefused as refused:
        print(f"NO SE COPIÓ NADA: {refused}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
