import os

import psycopg
import pytest


def connection() -> psycopg.Connection:
    return psycopg.connect(os.environ["DATABASE_URL"], prepare_threshold=None)


def test_games_rounds_and_questions_support_ordered_many_to_many_links() -> None:
    with connection() as conn:
        game_ids = [
            conn.execute("INSERT INTO game DEFAULT VALUES RETURNING id").fetchone()[0]
            for _ in range(2)
        ]
        round_ids = [
            conn.execute("INSERT INTO round DEFAULT VALUES RETURNING id").fetchone()[0]
            for _ in range(2)
        ]
        artist_id = conn.execute(
            "INSERT INTO artist (display_name) VALUES ('Artist') RETURNING id"
        ).fetchone()[0]
        track_id = conn.execute(
            "INSERT INTO track (artist_id) VALUES (%s) RETURNING id",
            (artist_id,),
        ).fetchone()[0]
        question_ids = [
            conn.execute(
                """
                INSERT INTO question (track_ids, artist_ids)
                VALUES (jsonb_build_array(%s::text), jsonb_build_array(%s::text))
                RETURNING id
                """,
                (track_id, artist_id),
            ).fetchone()[0]
            for _ in range(2)
        ]

        conn.execute(
            """
            INSERT INTO game_round (game_id, round_id, sequence_number)
            VALUES
                (%s, %s, 1),
                (%s, %s, 2),
                (%s, %s, 1)
            """,
            (game_ids[0], round_ids[0], game_ids[0], round_ids[1], game_ids[1], round_ids[0]),
        )
        conn.execute(
            """
            INSERT INTO round_question (round_id, question_id, sequence_number)
            VALUES
                (%s, %s, 1),
                (%s, %s, 2),
                (%s, %s, 1)
            """,
            (
                round_ids[0],
                question_ids[0],
                round_ids[0],
                question_ids[1],
                round_ids[1],
                question_ids[0],
            ),
        )

        assert conn.execute(
            "SELECT count(*) FROM game_round WHERE round_id = %s",
            (round_ids[0],),
        ).fetchone()[0] == 2
        assert conn.execute(
            "SELECT count(*) FROM round_question WHERE question_id = %s",
            (question_ids[0],),
        ).fetchone()[0] == 2


def test_relationship_links_reject_duplicate_parent_positions_and_pairs() -> None:
    with connection() as conn:
        game_id = conn.execute("INSERT INTO game DEFAULT VALUES RETURNING id").fetchone()[0]
        round_ids = [
            conn.execute("INSERT INTO round DEFAULT VALUES RETURNING id").fetchone()[0]
            for _ in range(2)
        ]
        conn.execute(
            """
            INSERT INTO game_round (game_id, round_id, sequence_number)
            VALUES (%s, %s, 1)
            """,
            (game_id, round_ids[0]),
        )

        with pytest.raises(psycopg.errors.UniqueViolation), conn.transaction():
            conn.execute(
                """
                INSERT INTO game_round (game_id, round_id, sequence_number)
                VALUES (%s, %s, 2)
                """,
                (game_id, round_ids[0]),
            )

        with pytest.raises(psycopg.errors.UniqueViolation), conn.transaction():
            conn.execute(
                """
                INSERT INTO game_round (game_id, round_id, sequence_number)
                VALUES (%s, %s, 1)
                """,
                (game_id, round_ids[1]),
            )


def test_round_has_no_direct_game_or_question_ownership_columns() -> None:
    with connection() as conn:
        assert conn.execute(
            """
            SELECT array_agg(column_name ORDER BY column_name)
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'round'
              AND column_name IN ('game_id', 'question_id', 'sequence_number')
            """
        ).fetchone()[0] is None
