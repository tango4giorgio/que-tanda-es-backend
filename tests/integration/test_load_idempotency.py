import os

import pytest

from src.repositories.db import connection

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL is required for Postgres integration tests",
)


def test_track_entry_has_duplicate_protection() -> None:
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT 1
                FROM pg_indexes
                WHERE schemaname = 'catalogue'
                  AND indexname = 'track_entry_orchestra_recording_unique'
                """
            )
            assert cursor.fetchone() is not None
