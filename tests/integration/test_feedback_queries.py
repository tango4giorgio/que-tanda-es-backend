import os
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb

from src.models.feedback import FeedbackSubmission
from src.repositories.db import connection
from src.repositories.feedback_repository import (
    DuplicateFeedbackError,
    FeedbackRepository,
    InvalidTrackPositionError,
)

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL is required for Postgres integration tests",
)


def _seed_question(conn, *, track_ids, choice_artist_ids) -> str:
    """Seed one aggregate question and its owning round."""
    with conn.cursor() as cursor:
        cursor.execute("INSERT INTO game DEFAULT VALUES RETURNING id")
        (game_id,) = cursor.fetchone()
        cursor.execute(
            "INSERT INTO question (track_ids, artist_ids) VALUES (%s, %s) RETURNING id",
            (Jsonb(track_ids), Jsonb(choice_artist_ids)),
        )
        (question_id,) = cursor.fetchone()
        cursor.execute(
            "INSERT INTO round DEFAULT VALUES RETURNING id"
        )
        (round_id,) = cursor.fetchone()
        cursor.execute(
            """
            INSERT INTO game_round (game_id, round_id, sequence_number)
            VALUES (%s, %s, 1)
            """,
            (str(game_id), str(round_id)),
        )
        cursor.execute(
            """
            INSERT INTO round_question (round_id, question_id, sequence_number)
            VALUES (%s, %s, 1)
            """,
            (str(round_id), str(question_id)),
        )
        return str(question_id)


def _seed_artist_and_track(conn) -> tuple[str, str]:
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
        return str(artist_id), str(track_id)


def _submit(
    conn, *, question_id, track_position, guessed_artist_id, outcome, elapsed_ms
) -> None:
    FeedbackRepository(conn).insert_attempt(
        FeedbackSubmission.model_validate(
            {
                "questionId": question_id,
                "trackPosition": track_position,
                "guessedArtistId": guessed_artist_id,
                "outcome": outcome,
                "elapsedMs": elapsed_ms,
            }
        )
    )


def test_get_by_track_id_returns_only_feedback_for_questions_presenting_that_track() -> None:
    with connection() as conn:
        artist_a, track_a = _seed_artist_and_track(conn)
        artist_b, track_b = _seed_artist_and_track(conn)
        artist_c, _track_c = _seed_artist_and_track(conn)

        question_one = _seed_question(
            conn, track_ids=[track_a], choice_artist_ids=[artist_a, artist_b, artist_c]
        )
        question_two = _seed_question(
            conn, track_ids=[track_a], choice_artist_ids=[artist_a, artist_b, artist_c]
        )
        unrelated_question = _seed_question(
            conn, track_ids=[track_b], choice_artist_ids=[artist_a, artist_b, artist_c]
        )

        _submit(
            conn,
            question_id=question_one,
            track_position=1,
            guessed_artist_id=artist_a,
            outcome="correct",
            elapsed_ms=4000,
        )
        _submit(
            conn,
            question_id=question_two,
            track_position=1,
            guessed_artist_id=artist_b,
            outcome="wrong",
            elapsed_ms=8000,
        )
        _submit(
            conn,
            question_id=unrelated_question,
            track_position=1,
            guessed_artist_id=artist_b,
            outcome="correct",
            elapsed_ms=2000,
        )

        feedback = FeedbackRepository(conn).get_by_track_id(track_a)

    assert {str(row.question_id) for row in feedback} == {question_one, question_two}
    assert unrelated_question not in {str(row.question_id) for row in feedback}


def test_get_by_artist_id_returns_feedback_for_any_question_offering_that_artist() -> None:
    with connection() as conn:
        artist_a, track_a = _seed_artist_and_track(conn)
        artist_b, track_b = _seed_artist_and_track(conn)
        artist_c, _track_c = _seed_artist_and_track(conn)

        # Artist A appears as a candidate on both questions (once correct, once a distractor).
        question_one = _seed_question(
            conn, track_ids=[track_a], choice_artist_ids=[artist_a, artist_b, artist_c]
        )
        question_two = _seed_question(
            conn, track_ids=[track_b], choice_artist_ids=[artist_a, artist_b, artist_c]
        )
        unrelated_question = _seed_question(
            conn, track_ids=[track_b], choice_artist_ids=[artist_b, artist_c, str(uuid4())]
        )

        _submit(
            conn,
            question_id=question_one,
            track_position=1,
            guessed_artist_id=artist_a,
            outcome="correct",
            elapsed_ms=4000,
        )
        _submit(
            conn,
            question_id=question_two,
            track_position=1,
            guessed_artist_id=artist_b,
            outcome="wrong",
            elapsed_ms=8000,
        )
        _submit(
            conn,
            question_id=unrelated_question,
            track_position=1,
            guessed_artist_id=artist_b,
            outcome="correct",
            elapsed_ms=2000,
        )

        feedback = FeedbackRepository(conn).get_by_artist_id(artist_a)

    assert {str(row.question_id) for row in feedback} == {question_one, question_two}
    assert unrelated_question not in {str(row.question_id) for row in feedback}


def test_one_question_accepts_feedback_for_each_track_position() -> None:
    with connection() as conn:
        artist_a, track_a = _seed_artist_and_track(conn)
        artist_b, track_b = _seed_artist_and_track(conn)
        artist_c, _track_c = _seed_artist_and_track(conn)
        question_id = _seed_question(
            conn,
            track_ids=[track_a, track_b],
            choice_artist_ids=[artist_a, artist_b, artist_c],
        )

        _submit(
            conn,
            question_id=question_id,
            track_position=1,
            guessed_artist_id=artist_a,
            outcome="correct",
            elapsed_ms=1000,
        )
        _submit(
            conn,
            question_id=question_id,
            track_position=2,
            guessed_artist_id=artist_b,
            outcome="wrong",
            elapsed_ms=2000,
        )

        track_a_positions = [
            row.track_position for row in FeedbackRepository(conn).get_by_track_id(track_a)
        ]
        track_b_positions = [
            row.track_position for row in FeedbackRepository(conn).get_by_track_id(track_b)
        ]
        assert track_a_positions == [1]
        assert track_b_positions == [2]


def test_feedback_rejects_duplicate_or_missing_track_position() -> None:
    with connection() as conn:
        artist_a, track_a = _seed_artist_and_track(conn)
        artist_b, _track_b = _seed_artist_and_track(conn)
        artist_c, _track_c = _seed_artist_and_track(conn)
        question_id = _seed_question(
            conn,
            track_ids=[track_a],
            choice_artist_ids=[artist_a, artist_b, artist_c],
        )
        _submit(
            conn,
            question_id=question_id,
            track_position=1,
            guessed_artist_id=artist_a,
            outcome="correct",
            elapsed_ms=1000,
        )

    with connection() as conn:
        with pytest.raises(DuplicateFeedbackError):
            _submit(
                conn,
                question_id=question_id,
                track_position=1,
                guessed_artist_id=artist_b,
                outcome="wrong",
                elapsed_ms=2000,
            )

    with connection() as conn:
        with pytest.raises(InvalidTrackPositionError):
            _submit(
                conn,
                question_id=question_id,
                track_position=2,
                guessed_artist_id=artist_b,
                outcome="wrong",
                elapsed_ms=2000,
            )
