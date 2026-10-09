import os
from uuid import uuid4

import pytest

from src.repositories.db import connection
from src.repositories.session_repository import SessionRepository

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL is required for Postgres integration tests",
)


def test_create_issues_distinct_unguessable_session_ids() -> None:
    with connection() as conn:
        repository = SessionRepository(conn)
        first = repository.create()
        second = repository.create()

    assert first.id != second.id
    assert first.started_at == first.last_interaction_at


def test_get_active_returns_a_freshly_created_session() -> None:
    with connection() as conn:
        repository = SessionRepository(conn)
        created = repository.create()

        found = repository.get_active(created.id)

    assert found is not None
    assert found.id == created.id


def test_get_active_returns_none_for_an_unknown_session() -> None:
    with connection() as conn:
        repository = SessionRepository(conn)

        found = repository.get_active(uuid4())

    assert found is None


def test_touch_advances_last_interaction_at_without_moving_started_at() -> None:
    with connection() as conn:
        repository = SessionRepository(conn)
        created = repository.create()

        touched = repository.touch(created.id)

    assert touched.started_at == created.started_at
    assert touched.last_interaction_at >= created.last_interaction_at


def test_get_active_returns_none_for_an_expired_session_while_the_row_remains_readable() -> None:
    with connection() as conn:
        repository = SessionRepository(conn)
        created = repository.create()

        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE session
                SET started_at = now() - interval '12 minutes',
                    last_interaction_at = now() - interval '11 minutes'
                WHERE id = %s
                """,
                (str(created.id),),
            )

        expired_lookup = repository.get_active(created.id)

        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM session WHERE id = %s", (str(created.id),))
            row = cursor.fetchone()

    assert expired_lookup is None
    assert row is not None
    assert row[0] == created.id
