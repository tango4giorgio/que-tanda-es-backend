import os

import pytest

from src.repositories.db import connection

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL is required for Postgres integration tests",
)


def test_catalogue_schema_is_available() -> None:
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT to_regclass('catalogue.track_entry')")
            assert cursor.fetchone()[0] == "catalogue.track_entry"
