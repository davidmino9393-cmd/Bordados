"""PostgreSQL con la misma interfaz que `Store` (SQLite): el resto de la API no sabe cuál de los dos usa."""
from pathlib import Path
from threading import RLock

import psycopg
from psycopg.rows import dict_row

from .store import Store

# Serializa las escrituras entre procesos como `BEGIN IMMEDIATE` entre conexiones de SQLite.
WRITE_LOCK_KEY = 7_212_015
SCHEMA = """
    CREATE TABLE IF NOT EXISTS resources(
        sequence BIGSERIAL PRIMARY KEY, kind TEXT NOT NULL, id TEXT NOT NULL,
        owner TEXT NOT NULL, project_id TEXT, body TEXT NOT NULL, private TEXT NOT NULL,
        UNIQUE(kind, id));
    CREATE INDEX IF NOT EXISTS resources_by_owner_project ON resources(kind, owner, project_id);
    CREATE TABLE IF NOT EXISTS idempotency(
        scope TEXT NOT NULL, key TEXT NOT NULL, fingerprint TEXT NOT NULL,
        status INTEGER NOT NULL, body TEXT NOT NULL, PRIMARY KEY(scope, key));
"""


class PostgresConnection:
    """La parte de `sqlite3.Connection` que usa `Store`: marcadores `?`, filas por nombre y `BEGIN IMMEDIATE`.

    Una sola conexión con las mismas reglas que SQLite (el `RLock` del almacén la usa de a una instrucción por vez).
    Si el servidor se reinicia entre dos pedidos, se reconecta una vez; si se corta en medio de una transacción no se
    reintenta nada: se pierde esa transacción y el error llega a quien la abrió, nunca un COMMIT a medias.
    """

    def __init__(self, url):
        self._url, self._in_transaction = url, False
        self._connect()

    def _connect(self):
        self._conn = psycopg.connect(self._url, autocommit=True, row_factory=dict_row)
        self._in_transaction = False

    @property
    def in_transaction(self):
        return self._in_transaction

    def execute(self, statement, params=()):
        try:
            return self._run(statement, params)
        except (psycopg.OperationalError, psycopg.InterfaceError):
            if not (self._conn.closed or self._conn.broken):
                raise
            was_in_transaction = self._in_transaction
            self._connect()
            if statement == "ROLLBACK":
                return None  # la conexión cortada ya descartó la transacción
            if was_in_transaction:
                raise
            return self._run(statement, params)

    def _run(self, statement, params):
        if statement == "BEGIN IMMEDIATE":
            self._conn.execute("BEGIN")
            self._in_transaction = True
            return self._conn.execute("SELECT pg_advisory_xact_lock(%s)", (WRITE_LOCK_KEY,))
        if statement in ("COMMIT", "ROLLBACK"):
            self._in_transaction = False
            return self._conn.execute(statement)
        return self._conn.execute(statement.replace("?", "%s"), params)

    def executemany(self, statement, rows):
        with self._conn.cursor() as cursor:
            cursor.executemany(statement.replace("?", "%s"), rows)

    def initialize(self):
        for statement in filter(None, (part.strip() for part in SCHEMA.split(";"))):
            self._conn.execute(statement)

    def close(self):
        self._conn.close()


class PostgresStore(Store):
    """`Store` sobre PostgreSQL. Los archivos (originales, JEF, vistas previas) siguen en `data_root`."""

    def __init__(self, data_root, database_url):
        self.root = Path(data_root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        self.db = PostgresConnection(database_url)
        self.db.initialize()
