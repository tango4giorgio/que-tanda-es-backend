from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb


class GameRepository:
    """Persists the `game`/`round` grouping structure a played session belongs to
    (data-model.md `game`, `round`; research.md §4, §5)."""

    def __init__(self, conn: Connection):
        self.conn = conn

    def create_game(self) -> UUID:
        with self.conn.cursor() as cursor:
            cursor.execute("INSERT INTO game DEFAULT VALUES RETURNING id")
            (game_id,) = cursor.fetchone()
        return game_id

    def create_question(
        self, track_ids: list[UUID], artist_ids: list[UUID]
    ) -> UUID:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO question (track_ids, artist_ids)
                VALUES (%s, %s)
                RETURNING id
                """,
                (
                    Jsonb([str(track_id) for track_id in track_ids]),
                    Jsonb([str(artist_id) for artist_id in artist_ids]),
                ),
            )
            (question_id,) = cursor.fetchone()
        return question_id

    def append_round(self, game_id: UUID, question_id: UUID) -> tuple[UUID, int]:
        """Create and link the next round for `game_id`.

        New gameplay records remain fresh even though the association tables permit rounds and
        questions to be shared.
        """
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO round DEFAULT VALUES
                RETURNING id
                """,
            )
            (round_id,) = cursor.fetchone()
            cursor.execute(
                """
                INSERT INTO game_round (game_id, round_id, sequence_number)
                VALUES (
                    %s,
                    %s,
                    COALESCE(
                        (
                            SELECT max(sequence_number)
                            FROM game_round
                            WHERE game_id = %s
                        ),
                        0
                    ) + 1
                )
                RETURNING sequence_number
                """,
                (str(game_id), str(round_id), str(game_id)),
            )
            (sequence_number,) = cursor.fetchone()
            cursor.execute(
                """
                INSERT INTO round_question (round_id, question_id, sequence_number)
                VALUES (%s, %s, 1)
                """,
                (str(round_id), str(question_id)),
            )
        return round_id, sequence_number
