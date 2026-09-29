import os
from uuid import UUID

import psycopg
import pytest


def connection() -> psycopg.Connection:
    return psycopg.connect(os.environ["DATABASE_URL"], prepare_threshold=None)


def _seed_artist(conn: psycopg.Connection, name: str, track_count: int) -> UUID:
    artist_id = conn.execute(
        "INSERT INTO artist (display_name) VALUES (%s) RETURNING id",
        (name,),
    ).fetchone()[0]
    for position in range(track_count):
        track_id = conn.execute(
            "INSERT INTO track (artist_id) VALUES (%s) RETURNING id",
            (artist_id,),
        ).fetchone()[0]
        conn.execute(
            """
            INSERT INTO track_provider (
                track_id, provider, provider_track_id, title, duration_ms
            )
            VALUES (%s, 'deezer', %s, %s, 30000)
            """,
            (track_id, f"{name}-{position}", f"{name} track {position}"),
        )
    return artist_id


def test_create_question_for_artist_uses_requested_tracks_and_choices() -> None:
    with connection() as conn:
        correct_artist_id = _seed_artist(conn, "Correct", 3)
        distractor_ids = {
            _seed_artist(conn, "Distractor A", 1),
            _seed_artist(conn, "Distractor B", 1),
            _seed_artist(conn, "Distractor C", 1),
        }

        row = conn.execute(
            "SELECT id, track_ids, artist_ids FROM create_question_for_artist(2, 4, %s)",
            (correct_artist_id,),
        ).fetchone()

        track_ids = [UUID(value) for value in row[1]]
        artist_ids = [UUID(value) for value in row[2]]
        owners = {
            owner
            for (owner,) in conn.execute(
                "SELECT artist_id FROM track WHERE id = ANY(%s::uuid[])",
                ([str(track_id) for track_id in track_ids],),
            )
        }

        assert len(track_ids) == 2
        assert owners == {correct_artist_id}
        assert len(artist_ids) == 4
        assert len(set(artist_ids)) == 4
        assert correct_artist_id in artist_ids
        assert set(artist_ids) == {correct_artist_id, *distractor_ids}
        assert conn.execute(
            "SELECT count(*) FROM question WHERE id = %s", (row[0],)
        ).fetchone()[0] == 1


def test_create_random_question_uses_three_tracks_and_three_choices() -> None:
    with connection() as conn:
        eligible_artist_id = _seed_artist(conn, "Eligible", 3)
        _seed_artist(conn, "Distractor A", 1)
        _seed_artist(conn, "Distractor B", 1)

        row = conn.execute(
            "SELECT track_ids, artist_ids FROM create_random_question()"
        ).fetchone()

        track_ids = [UUID(value) for value in row[0]]
        artist_ids = [UUID(value) for value in row[1]]
        owners = {
            owner
            for (owner,) in conn.execute(
                "SELECT artist_id FROM track WHERE id = ANY(%s::uuid[])",
                ([str(track_id) for track_id in track_ids],),
            )
        }

        assert len(track_ids) == 3
        assert len(artist_ids) == 3
        assert owners == {eligible_artist_id}
        assert eligible_artist_id in artist_ids


@pytest.mark.parametrize(
    ("tracks", "choices"),
    [(0, 3), (4, 3), (1, 0)],
)
def test_create_question_for_artist_rejects_invalid_counts(
    tracks: int, choices: int
) -> None:
    with connection() as conn:
        artist_id = _seed_artist(conn, "Artist", 3)
        with pytest.raises(psycopg.errors.InvalidParameterValue):
            conn.execute(
                "SELECT create_question_for_artist(%s, %s, %s)",
                (tracks, choices, artist_id),
            )
        conn.rollback()


def test_create_question_for_artist_rejects_insufficient_tracks_or_choices() -> None:
    with connection() as conn:
        artist_id = _seed_artist(conn, "Artist", 1)
        _seed_artist(conn, "Only distractor", 1)

        with pytest.raises(psycopg.errors.InvalidParameterValue):
            conn.execute(
                "SELECT create_question_for_artist(2, 2, %s)",
                (artist_id,),
            )
        conn.rollback()

    with connection() as conn:
        artist_id = _seed_artist(conn, "Artist", 1)
        with pytest.raises(psycopg.errors.InvalidParameterValue):
            conn.execute(
                "SELECT create_question_for_artist(1, 3, %s)",
                (artist_id,),
            )
        conn.rollback()
