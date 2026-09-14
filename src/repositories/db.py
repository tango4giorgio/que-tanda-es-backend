from collections.abc import Iterator
from contextlib import contextmanager

import psycopg

from src.config import database_url


@contextmanager
def connection() -> Iterator[psycopg.Connection]:
    with psycopg.connect(database_url()) as conn:
        yield conn
