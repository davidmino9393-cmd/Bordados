"""SQLite metadata and exact idempotent response replay for one API process."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
from threading import RLock

from .errors import ApiProblem


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class Store:
    def __init__(self, data_root):
        self.root = Path(data_root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        self.db = sqlite3.connect(self.root / "metadata.sqlite3", check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS resources(
                sequence INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, id TEXT NOT NULL,
                owner TEXT NOT NULL, project_id TEXT, body TEXT NOT NULL, private TEXT NOT NULL,
                UNIQUE(kind,id));
            CREATE TABLE IF NOT EXISTS idempotency(
                scope TEXT NOT NULL, key TEXT NOT NULL, fingerprint TEXT NOT NULL,
                status INTEGER NOT NULL, body TEXT NOT NULL, PRIMARY KEY(scope,key));
        """)

    @contextmanager
    def transaction(self):
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield
                self.db.execute("COMMIT")
            except BaseException:
                self.db.execute("ROLLBACK")
                raise

    def create(self, kind, identifier, owner, project_id, body, private=None):
        with self.lock:
            self.db.execute("INSERT INTO resources(kind,id,owner,project_id,body,private) VALUES(?,?,?,?,?,?)",
                            (kind, identifier, owner, project_id, canonical(body), canonical(private or {})))

    def update(self, kind, identifier, body, private=None):
        with self.lock:
            if private is None:
                self.db.execute("UPDATE resources SET body=? WHERE kind=? AND id=?", (canonical(body), kind, identifier))
            else:
                self.db.execute("UPDATE resources SET body=?,private=? WHERE kind=? AND id=?", (canonical(body), canonical(private), kind, identifier))

    def mutate(self, kind, identifier, change):
        """Lectura, cambio y escritura de un recurso en una sola transacción.

        `change(body, private)` recibe lo que hay guardado AHORA y devuelve `(body, private)` para escribir, o None para
        no escribir. Si lanza, no se escribe nada. Sirve a quien escribe sobre lo que otro pudo cambiar un instante antes
        (el worker y la cancelación sobre el mismo job): ninguna de las dos escrituras pisa a la otra. Si ya hay una
        transacción abierta (la de `idempotent`), se une a ella en vez de abrir otra.
        """
        with self.lock:
            opened = not self.db.in_transaction
            if opened:
                self.db.execute("BEGIN IMMEDIATE")
            try:
                current = self.get(kind, identifier)
                result = change(current["body"], current["private"])
                if result is not None:
                    self.update(kind, identifier, *result)
                if opened:
                    self.db.execute("COMMIT")
            except BaseException:
                if opened:
                    self.db.execute("ROLLBACK")
                raise

    def get(self, kind, identifier, owner=None):
        with self.lock:
            row = self.db.execute("SELECT * FROM resources WHERE kind=? AND id=?", (kind, identifier)).fetchone()
        if row is None or (owner is not None and row["owner"] != owner):
            raise ApiProblem("NOT_FOUND", "El recurso no está disponible para este usuario.")
        return dict(row, body=json.loads(row["body"]), private=json.loads(row["private"]))

    def rows(self, kind, owner=None, project_id=None):
        query, values = "SELECT * FROM resources WHERE kind=?", [kind]
        for name, value in (("owner", owner), ("project_id", project_id)):
            if value is not None:
                query += f" AND {name}=?"
                values.append(value)
        with self.lock:
            rows = self.db.execute(query + " ORDER BY sequence", values).fetchall()
        return [dict(row, body=json.loads(row["body"]), private=json.loads(row["private"])) for row in rows]

    def idempotent(self, scope, key, logical_content, action):
        if not key or len(key) > 128:
            raise ApiProblem("INVALID_REQUEST", "Idempotency-Key es obligatorio y admite hasta 128 caracteres.")
        fingerprint = hashlib.sha256(canonical(logical_content).encode()).hexdigest()
        with self.transaction():
            row = self.db.execute("SELECT * FROM idempotency WHERE scope=? AND key=?", (scope, key)).fetchone()
            if row:
                if row["fingerprint"] != fingerprint:
                    raise ApiProblem("IDEMPOTENCY_CONFLICT", "La clave ya identifica otro contenido.")
                return row["status"], json.loads(row["body"])
            status, body = action()
            self.db.execute("INSERT INTO idempotency VALUES(?,?,?,?,?)", (scope, key, fingerprint, status, canonical(body)))
            return status, body

    def close(self):
        with self.lock:
            self.db.close()


def open_store(data_root, database_url=None):
    """SQLite dentro de `data_root` o, con `database_url`, PostgreSQL; los archivos quedan siempre en `data_root`."""
    if not database_url:
        return Store(data_root)
    from .store_postgres import PostgresStore  # recién acá: quien usa SQLite no necesita psycopg

    return PostgresStore(data_root, database_url)
