import os
import sqlite3
from typing import Any, Dict, Iterable, Optional
from .schema import SCHEMA_SQL
from .migrations import run_migrations


_conn: Optional[sqlite3.Connection] = None
_db_path: Optional[str] = None


def get_conn(db_path: str) -> sqlite3.Connection:
    global _conn, _db_path
    if _conn is None:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        _conn = sqlite3.connect(db_path)
        _conn.row_factory = sqlite3.Row
        _db_path = db_path
    return _conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    run_migrations(conn)


def execute(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> int:
    cur = conn.execute(sql, list(params))
    conn.commit()
    return cur.lastrowid or 0


def query_all(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()):
    cur = conn.execute(sql, list(params))
    return [dict(r) for r in cur.fetchall()]


def query_one(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()):
    cur = conn.execute(sql, list(params))
    row = cur.fetchone()
    return dict(row) if row else None


def get_queue_size(conn: sqlite3.Connection) -> int:
    row = query_one(conn, "SELECT COUNT(1) AS c FROM queue WHERE status IN ('pending','scheduled','ready')")
    return int(row['c']) if row else 0
