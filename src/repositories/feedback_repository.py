from uuid import UUID

from psycopg import Connection, errors

from src.models.feedback import FeedbackSubmission, GuessFeedback


class FeedbackRejectedError(RuntimeError):
    """Base class for guess feedback submissions rejected by the database."""


class DuplicateFeedbackError(FeedbackRejectedError):
    """The referenced question already has a recorded guess feedback row (FR-007)."""


class UnknownQuestionError(FeedbackRejectedError):
    """The referenced question_id does not reference an existing question."""


class InvalidTrackPositionError(FeedbackRejectedError):
    """The requested track position is not present in the aggregate question."""


class FeedbackRepository:
    """Insert-only repository for anonymous guess feedback rows, plus the read-only
    track/artist queries needed for User Story 3's accuracy analysis."""

    def __init__(self, conn: Connection):
        self.conn = conn

    def insert_attempt(
        self, submission: FeedbackSubmission, session_id: UUID | None
    ) -> None:
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO guess_feedback
                        (question_id, track_position, guessed_artist_id, outcome, elapsed_ms, session_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(submission.question_id),
                        submission.track_position,
                        str(submission.guessed_artist_id)
                        if submission.guessed_artist_id
                        else None,
                        submission.outcome,
                        submission.elapsed_ms,
                        str(session_id) if session_id else None,
                    ),
                )
        except errors.UniqueViolation as error:
            raise DuplicateFeedbackError from error
        except errors.ForeignKeyViolation as error:
            raise UnknownQuestionError from error
        except errors.CheckViolation as error:
            raise InvalidTrackPositionError from error

    def _rows_to_feedback(self, rows: list[tuple]) -> list[GuessFeedback]:
        return [
            GuessFeedback(
                id=row[0],
                question_id=row[1],
                track_position=row[2],
                guessed_artist_id=row[3],
                outcome=row[4],
                elapsed_ms=row[5],
                created_at=row[6],
                updated_at=row[7],
                session_id=row[8],
            )
            for row in rows
        ]

    def get_by_track_id(self, track_id: UUID) -> list[GuessFeedback]:
        """Return every guess feedback row for questions presenting `track_id`
        (data-model.md relationships summary; SC-002)."""
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT gf.id, gf.question_id, gf.track_position, gf.guessed_artist_id,
                       gf.outcome, gf.elapsed_ms, gf.created_at, gf.updated_at, gf.session_id
                FROM guess_feedback AS gf
                JOIN question AS q ON q.id = gf.question_id
                WHERE q.track_ids ->> (gf.track_position - 1) = %s
                ORDER BY gf.created_at
                """,
                (str(track_id),),
            )
            rows = cursor.fetchall()
        return self._rows_to_feedback(rows)

    def get_by_artist_id(self, artist_id: UUID) -> list[GuessFeedback]:
        """Return every guess feedback row for questions that offered `artist_id` as a
        candidate choice (data-model.md relationships summary; SC-002)."""
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT gf.id, gf.question_id, gf.track_position, gf.guessed_artist_id,
                       gf.outcome, gf.elapsed_ms, gf.created_at, gf.updated_at, gf.session_id
                FROM guess_feedback AS gf
                JOIN question AS q ON q.id = gf.question_id
                WHERE q.artist_ids ? %s
                ORDER BY gf.created_at
                """,
                (str(artist_id),),
            )
            rows = cursor.fetchall()
        return self._rows_to_feedback(rows)
