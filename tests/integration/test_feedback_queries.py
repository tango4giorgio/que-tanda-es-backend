import os
from uuid import uuid4

import pytest

from src.repositories.db import connection

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL is required for Postgres integration tests",
)


def _insert_attempt(
    conn,
    *,
    round_token: str,
    track_position: int,
    correct_artist_id,
    outcome: str,
    elapsed_ms: int,
) -> None:
    guessed_artist_id = None if outcome == "skipped" else correct_artist_id
    conn.execute(
        """
        INSERT INTO feedback.guess_attempt
            (round_token, track_position, recording_id, correct_artist_id,
             guessed_artist_id, outcome, elapsed_ms)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            round_token,
            track_position,
            str(uuid4()),
            str(correct_artist_id),
            str(guessed_artist_id) if guessed_artist_id else None,
            outcome,
            elapsed_ms,
        ),
    )


def test_feedback_queries_compute_accuracy_and_average_elapsed_per_artist_and_position() -> None:
    artist_a = uuid4()
    artist_b = uuid4()

    with connection() as conn:
        # Artist A: two attempts at track position 1 (one correct, one wrong).
        _insert_attempt(
            conn,
            round_token=f"round-{uuid4().hex}",
            track_position=1,
            correct_artist_id=artist_a,
            outcome="correct",
            elapsed_ms=4000,
        )
        _insert_attempt(
            conn,
            round_token=f"round-{uuid4().hex}",
            track_position=1,
            correct_artist_id=artist_a,
            outcome="wrong",
            elapsed_ms=8000,
        )
        # Artist B: one correct attempt at track position 2, one skip at track position 2.
        _insert_attempt(
            conn,
            round_token=f"round-{uuid4().hex}",
            track_position=2,
            correct_artist_id=artist_b,
            outcome="correct",
            elapsed_ms=2000,
        )
        _insert_attempt(
            conn,
            round_token=f"round-{uuid4().hex}",
            track_position=2,
            correct_artist_id=artist_b,
            outcome="skipped",
            elapsed_ms=30000,
        )

        by_artist = {
            row[0]: {"accuracy": row[1], "avg_elapsed_ms": row[2]}
            for row in conn.execute(
                """
                SELECT correct_artist_id::text,
                       avg((outcome = 'correct')::int)::float AS accuracy,
                       avg(elapsed_ms)::float AS avg_elapsed_ms
                FROM feedback.guess_attempt
                WHERE correct_artist_id IN (%s, %s)
                GROUP BY correct_artist_id
                """,
                (str(artist_a), str(artist_b)),
            ).fetchall()
        }

        by_position = {
            row[0]: {"accuracy": row[1], "avg_elapsed_ms": row[2]}
            for row in conn.execute(
                """
                SELECT track_position,
                       avg((outcome = 'correct')::int)::float AS accuracy,
                       avg(elapsed_ms)::float AS avg_elapsed_ms
                FROM feedback.guess_attempt
                WHERE correct_artist_id IN (%s, %s)
                GROUP BY track_position
                """,
                (str(artist_a), str(artist_b)),
            ).fetchall()
        }

    assert by_artist[str(artist_a)]["accuracy"] == pytest.approx(0.5)
    assert by_artist[str(artist_a)]["avg_elapsed_ms"] == pytest.approx(6000)
    assert by_artist[str(artist_b)]["accuracy"] == pytest.approx(0.5)
    assert by_artist[str(artist_b)]["avg_elapsed_ms"] == pytest.approx(16000)

    assert by_position[1]["accuracy"] == pytest.approx(0.5)
    assert by_position[1]["avg_elapsed_ms"] == pytest.approx(6000)
    assert by_position[2]["accuracy"] == pytest.approx(0.5)
    assert by_position[2]["avg_elapsed_ms"] == pytest.approx(16000)
