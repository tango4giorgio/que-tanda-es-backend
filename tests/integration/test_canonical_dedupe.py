import os

import pytest

from src.repositories.db import connection

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL is required for Postgres integration tests",
)


def test_musicbrainz_recording_is_the_only_local_music_identity() -> None:
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'catalogue'
                  AND table_name = 'recording_provider'
                  AND column_name = 'musicbrainz_recording_id'
                """
            )
            assert cursor.fetchone() is not None
            cursor.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema IN ('catalogue', 'music')
                  AND table_name IN ('artist', 'recording', 'orchestra', 'track_entry')
                """
            )
            assert cursor.fetchall() == []
