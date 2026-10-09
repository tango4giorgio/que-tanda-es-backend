from uuid import UUID

from src.models.session import Session, SessionCreated
from src.repositories.session_repository import SessionRepository


class InvalidSessionError(RuntimeError):
    """Raised when `X-Session-Id` is missing, malformed, unknown, or expired (FR-003,
    FR-004); handlers map this to `401 SESSION_INVALID`."""


class SessionService:
    def __init__(self, repository: SessionRepository):
        self.repository = repository

    def create_session(self) -> SessionCreated:
        session = self.repository.create()
        return SessionCreated(session_id=session.id, started_at=session.started_at)

    def require_active_session(self, session_id_header: str | None) -> Session:
        """Validate the session referenced by an `X-Session-Id` header value without
        modifying it. Raises `InvalidSessionError` for a missing, malformed, unknown, or
        expired value (FR-004, FR-008); callers should call `touch` after their own
        activity action succeeds (FR-006)."""
        if not session_id_header:
            raise InvalidSessionError
        try:
            session_id = UUID(session_id_header)
        except ValueError as error:
            raise InvalidSessionError from error

        session = self.repository.get_active(session_id)
        if session is None:
            raise InvalidSessionError
        return session

    def touch(self, session_id: UUID) -> Session:
        """Advance the session's `last_interaction_at` to now (FR-006). Called only after
        the caller's own activity action has already succeeded."""
        return self.repository.touch(session_id)
