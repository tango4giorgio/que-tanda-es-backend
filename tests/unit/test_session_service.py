from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from src.models.session import Session
from src.services.session_service import InvalidSessionError, SessionService

FIXED_TIME = datetime(2024, 1, 1, tzinfo=UTC)


def sample_session(session_id: UUID) -> Session:
    return Session(
        id=session_id,
        started_at=FIXED_TIME,
        last_interaction_at=FIXED_TIME,
        created_at=FIXED_TIME,
        updated_at=FIXED_TIME,
    )


class FakeSessionRepository:
    def __init__(self, active_sessions: dict[UUID, Session] | None = None):
        self.active_sessions = active_sessions or {}
        self.created: list[Session] = []
        self.touched: list[UUID] = []

    def create(self) -> Session:
        session = sample_session(uuid4())
        self.created.append(session)
        return session

    def get_active(self, session_id: UUID) -> Session | None:
        return self.active_sessions.get(session_id)

    def touch(self, session_id: UUID) -> Session:
        self.touched.append(session_id)
        session = self.active_sessions[session_id]
        return session


def test_create_session_returns_the_repository_created_session_as_sessioncreated() -> None:
    repository = FakeSessionRepository()

    created = SessionService(repository).create_session()

    assert created.session_id == repository.created[0].id
    assert created.started_at == repository.created[0].started_at


def test_require_active_session_returns_the_session_for_a_known_active_id() -> None:
    session_id = uuid4()
    repository = FakeSessionRepository({session_id: sample_session(session_id)})

    session = SessionService(repository).require_active_session(str(session_id))

    assert session.id == session_id


def test_require_active_session_rejects_a_missing_header() -> None:
    repository = FakeSessionRepository()

    with pytest.raises(InvalidSessionError):
        SessionService(repository).require_active_session(None)


def test_require_active_session_rejects_an_empty_header() -> None:
    repository = FakeSessionRepository()

    with pytest.raises(InvalidSessionError):
        SessionService(repository).require_active_session("")


def test_require_active_session_rejects_a_malformed_header() -> None:
    repository = FakeSessionRepository()

    with pytest.raises(InvalidSessionError):
        SessionService(repository).require_active_session("not-a-uuid")


def test_require_active_session_rejects_an_unknown_or_expired_session() -> None:
    repository = FakeSessionRepository()

    with pytest.raises(InvalidSessionError):
        SessionService(repository).require_active_session(str(uuid4()))


def test_touch_delegates_to_the_repository() -> None:
    session_id = uuid4()
    repository = FakeSessionRepository({session_id: sample_session(session_id)})

    touched = SessionService(repository).touch(session_id)

    assert touched.id == session_id
    assert repository.touched == [session_id]
