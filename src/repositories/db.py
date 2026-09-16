from collections.abc import Iterator
from contextlib import contextmanager
from threading import Lock

import psycopg

from src.config import (
    database_connect_timeout_seconds,
    database_statement_timeout_ms,
    database_url,
)

_connection: psycopg.Connection | None = None
_connection_lock = Lock()


def _new_connection() -> psycopg.Connection:
    return psycopg.connect(
        database_url(),
        connect_timeout=database_connect_timeout_seconds(),
        options=f"-c statement_timeout={database_statement_timeout_ms()}",
        prepare_threshold=None,
    )


def _is_healthy(conn: psycopg.Connection) -> bool:
    if conn.closed or conn.broken:
        return False
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except psycopg.Error:
        return False
    return True


def get_connection() -> psycopg.Connection:
    global _connection
    with _connection_lock:
        if _connection is None or not _is_healthy(_connection):
            if _connection is not None:
                _connection.close()
            _connection = _new_connection()
        return _connection


@contextmanager
def connection() -> Iterator[psycopg.Connection]:
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
