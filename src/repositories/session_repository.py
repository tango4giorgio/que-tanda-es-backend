from uuid import UUID

from psycopg import Connection

from src.models.session import Session


class SessionRepository:
    """Creates sessions and reads/refreshes them for gameplay activity actions."""

    def __init__(self, conn: Connection):
        self.conn = conn

    def _row_to_session(self, row: tuple) -> Session:
        return Session(
            id=row[0],
            started_at=row[1],
            last_interaction_at=row[2],
            created_at=row[3],
            updated_at=row[4],
        )

    def create(self) -> Session:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO session DEFAULT VALUES
                RETURNING id, started_at, last_interaction_at, created_at, updated_at
                """
            )
            row = cursor.fetchone()
        return self._row_to_session(row)

    def get_active(self, session_id: UUID) -> Session | None:
        """Return the session referenced by `session_id`, but only when it exists and is
        not expired (`last_interaction_at >= now() - interval '10 minutes'`, FR-007, FR-008).
        Returns `None` for an unknown or expired session."""
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, started_at, last_interaction_at, created_at, updated_at
                FROM session
                WHERE id = %s AND last_interaction_at >= now() - interval '10 minutes'
                """,
                (str(session_id),),
            )
            row = cursor.fetchone()
        return self._row_to_session(row) if row else None

    def touch(self, session_id: UUID) -> Session:
        """Advance `last_interaction_at` to now for `session_id` (FR-006). Called only after
        an activity action has already succeeded for a session validated by `get_active`."""
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE session
                SET last_interaction_at = now()
                WHERE id = %s
                RETURNING id, started_at, last_interaction_at, created_at, updated_at
                """,
                (str(session_id),),
            )
            row = cursor.fetchone()
        return self._row_to_session(row)
