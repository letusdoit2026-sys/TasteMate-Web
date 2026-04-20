"""
Postgres database module for TasteMate Web.

- Uses psycopg3 with connection pooling.
- Replaces the old SQLite `get_db() / init_db()` helpers in app.py.
- Exposes dict-row cursors so existing `row["colname"]` access in app.py
  continues to work unchanged.
"""

import os
import atexit
from flask import g
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row


DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://praveengiri@localhost:5432/tastemate_web",
)

# Module-level pool — created once at import time.
_pool = ConnectionPool(
    conninfo=DATABASE_URL,
    min_size=1,
    max_size=10,
    kwargs={"row_factory": dict_row},
    open=True,
)
atexit.register(_pool.close)


class _DBWrapper:
    """
    Thin wrapper that mimics the SQLite connection API used in app.py:

        db = get_db()
        row = db.execute("SELECT ... WHERE id = %s", (x,)).fetchone()
        db.execute("INSERT ...", (...))
        db.commit()

    Under the hood, each `.execute()` call leases a cursor from a pooled
    connection and runs inside an implicit transaction that commits on
    `.commit()` or auto-closes on teardown.
    """

    def __init__(self):
        self._conn = _pool.getconn()
        # autocommit OFF — app.py calls db.commit() explicitly.
        self._conn.autocommit = False

    def execute(self, query, params=()):
        cur = self._conn.cursor()
        cur.execute(query, params)
        return _Cursor(cur)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        try:
            self._conn.rollback()  # discard any uncommitted work
        except Exception:
            pass
        _pool.putconn(self._conn)


class _Cursor:
    """Small shim so `.execute(...).fetchone()` / `.fetchall()` still works."""

    def __init__(self, cur):
        self._cur = cur

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def lastrowid(self):
        return None


def get_db():
    """Flask request-scoped DB handle. Call from within an app context."""
    if "db" not in g:
        g.db = _DBWrapper()
    return g.db


def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Run schema.sql to create tables if they don't exist."""
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    with _pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(schema_sql)
        conn.commit()
