import os
from uuid import uuid4

import psycopg
import pytest

from src.repositories.db import connection

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL is required for Postgres integration tests",
)


def _insert_artist_and_track(conn) -> str:
    with conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO artist (display_name) VALUES (%s) RETURNING id",
            (f"Test Artist {uuid4()}",),
        )
        (artist_id,) = cursor.fetchone()
        cursor.execute(
            "INSERT INTO track (artist_id) VALUES (%s) RETURNING id",
            (str(artist_id),),
        )
        (track_id,) = cursor.fetchone()
        return str(track_id)


def test_track_provider_rejects_a_duplicate_provider_track_id_for_the_same_track() -> None:
    provider_track_id = str(uuid4())
    with connection() as conn:
        track_id = _insert_artist_and_track(conn)
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO track_provider (track_id, provider, provider_track_id)
                VALUES (%s, 'deezer', %s)
                """,
                (track_id, provider_track_id),
            )

        with pytest.raises(psycopg.errors.UniqueViolation):
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO track_provider (track_id, provider, provider_track_id)
                    VALUES (%s, 'deezer', %s)
                    """,
                    (track_id, provider_track_id),
                )
        conn.rollback()


def test_track_provider_allows_the_same_provider_track_id_for_a_different_provider() -> None:
    provider_track_id = str(uuid4())
    with connection() as conn:
        track_id = _insert_artist_and_track(conn)
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO track_provider (track_id, provider, provider_track_id)
                VALUES (%s, 'deezer', %s)
                """,
                (track_id, provider_track_id),
            )
            cursor.execute(
                """
                INSERT INTO track_provider (track_id, provider, provider_track_id)
                VALUES (%s, 'test-provider', %s)
                """,
                (track_id, provider_track_id),
            )
            cursor.execute(
                "SELECT count(*) FROM track_provider WHERE track_id = %s",
                (track_id,),
            )
            (count,) = cursor.fetchone()
            assert count == 2
