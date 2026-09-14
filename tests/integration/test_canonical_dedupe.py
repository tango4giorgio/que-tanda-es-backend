import os

import pytest

from src.repositories.db import connection

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL is required for Postgres integration tests",
)


def test_canonical_recording_link_column_exists() -> None:
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'catalogue'
                  AND table_name = 'track_entry'
                  AND column_name = 'recording_id'
                """
            )
            assert cursor.fetchone() is not None
