from psycopg import Connection

from src.models.feedback import FeedbackSubmission


class FeedbackRepository:
    """Insert-only repository for anonymous guess feedback rows. There is
    deliberately no read/query surface here; querying the recorded data for
    analysis (User Story 3) is done directly against the database, not
    through application code, since this repository's only job is to
    persist each attempt exactly once."""

    def __init__(self, conn: Connection):
        self.conn = conn

    def insert_attempt(self, submission: FeedbackSubmission) -> None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO feedback.guess_attempt (
                    round_token,
                    track_position,
                    recording_id,
                    correct_artist_id,
                    guessed_artist_id,
                    outcome,
                    elapsed_ms
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    submission.round_token,
                    submission.track_position,
                    str(submission.recording_id),
                    str(submission.correct_artist_id),
                    str(submission.guessed_artist_id) if submission.guessed_artist_id else None,
                    submission.outcome,
                    submission.elapsed_ms,
                ),
            )
