import os
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb


def connection() -> psycopg.Connection:
    return psycopg.connect(os.environ["DATABASE_URL"], prepare_threshold=None)


def _seed_artist(conn: psycopg.Connection, name: str) -> UUID:
    return conn.execute(
        "INSERT INTO artist (display_name) VALUES (%s) RETURNING id",
        (name,),
    ).fetchone()[0]


def _seed_track(
    conn: psycopg.Connection,
    artist_id: UUID,
    provider: str,
    provider_track_id: str,
    title: str,
) -> UUID:
    track_id = conn.execute(
        "INSERT INTO track (artist_id) VALUES (%s) RETURNING id",
        (artist_id,),
    ).fetchone()[0]
    conn.execute(
        """
        INSERT INTO track_provider (
            track_id, provider, provider_track_id, title, duration_ms
        )
        VALUES (%s, %s, %s, %s, 30000)
        """,
        (track_id, provider, provider_track_id, title),
    )
    return track_id


def test_admin_question_shows_ordered_titles_choices_and_correct_artist() -> None:
    with connection() as conn:
        correct_artist_id = _seed_artist(conn, "Correct Orchestra")
        distractor_a_id = _seed_artist(conn, "Distractor A")
        distractor_b_id = _seed_artist(conn, "Distractor B")
        first_track_id = _seed_track(
            conn,
            correct_artist_id,
            "archive",
            "archive-first",
            "Archive First",
        )
        second_track_id = _seed_track(
            conn,
            correct_artist_id,
            "deezer",
            "deezer-second",
            "Deezer Second",
        )
        conn.execute(
            """
            INSERT INTO track_provider (
                track_id, provider, provider_track_id, title, duration_ms
            )
            VALUES (%s, 'deezer', 'deezer-first', 'Deezer First', 30000)
            """,
            (first_track_id,),
        )
        question_id = conn.execute(
            """
            INSERT INTO question (track_ids, artist_ids)
            VALUES (%s, %s)
            RETURNING id
            """,
            (
                Jsonb([str(second_track_id), str(first_track_id)]),
                Jsonb(
                    [
                        str(distractor_a_id),
                        str(correct_artist_id),
                        str(distractor_b_id),
                    ]
                ),
            ),
        ).fetchone()[0]

        row = conn.execute(
            """
            SELECT tracks, artists, correct_artist_id, correct_artist_name
            FROM admin_question
            WHERE question_id = %s
            """,
            (question_id,),
        ).fetchone()

        assert row[0] == [
            {"trackId": str(second_track_id), "title": "Deezer Second"},
            {"trackId": str(first_track_id), "title": "Deezer First"},
        ]
        assert row[1] == [
            {"artistId": str(distractor_a_id), "name": "Distractor A"},
            {"artistId": str(correct_artist_id), "name": "Correct Orchestra"},
            {"artistId": str(distractor_b_id), "name": "Distractor B"},
        ]
        assert row[2] == correct_artist_id
        assert row[3] == "Correct Orchestra"


def test_admin_question_keeps_track_when_no_provider_title_exists() -> None:
    with connection() as conn:
        artist_id = _seed_artist(conn, "Untitled Orchestra")
        track_id = _seed_track(
            conn,
            artist_id,
            "deezer",
            "untitled-track",
            "Temporary title",
        )
        conn.execute(
            "UPDATE track_provider SET title = NULL WHERE track_id = %s",
            (track_id,),
        )
        question_id = conn.execute(
            """
            INSERT INTO question (track_ids, artist_ids)
            VALUES (%s, %s)
            RETURNING id
            """,
            (Jsonb([str(track_id)]), Jsonb([str(artist_id)])),
        ).fetchone()[0]

        tracks = conn.execute(
            "SELECT tracks FROM admin_question WHERE question_id = %s",
            (question_id,),
        ).fetchone()[0]

        assert tracks == [{"trackId": str(track_id), "title": None}]
