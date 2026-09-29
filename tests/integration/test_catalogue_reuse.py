import os
from random import Random
from uuid import uuid4

import pytest

from src.models.round import GameRequest
from src.repositories.catalogue_repository import CatalogueRepository
from src.repositories.db import connection
from src.repositories.game_repository import GameRepository
from src.services.game_service import GameService

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL is required for Postgres integration tests",
)


def _seed_eligible_artist(conn) -> None:
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
        cursor.execute(
            """
            INSERT INTO track_provider
                (track_id, provider, provider_track_id, title, duration_ms)
            VALUES (%s, 'archive.org', %s, 'Test Track', 180000)
            """,
            (str(track_id), f"item-{uuid4().hex}"),
        )


def test_two_separate_games_questions_reference_the_identical_seeded_catalogue_rows() -> None:
    """Seed one artist, track, and track_provider once (per two more distractor artists to
    satisfy round selection's minimum of three eligible artists), generate two separate games,
    and assert both games' questions reference the identical underlying rows rather than
    duplicating them (User Story 2 acceptance scenarios 1-2; SC-004)."""
    with connection() as conn:
        for _ in range(3):
            _seed_eligible_artist(conn)

    with connection() as conn:
        service = GameService(
            CatalogueRepository(conn), GameRepository(conn), conn, random_source=Random(1234)
        )
        first_response = service.create_game(GameRequest())
    with connection() as conn:
        service = GameService(
            CatalogueRepository(conn), GameRepository(conn), conn, random_source=Random(1234)
        )
        second_response = service.create_game(GameRequest())

    first_question_id = first_response.rounds[0].question.question_id
    second_question_id = second_response.rounds[0].question.question_id
    assert first_question_id != second_question_id

    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, track_ids FROM question WHERE id = ANY(%s::uuid[])",
                ([str(first_question_id), str(second_question_id)],),
            )
            rows = cursor.fetchall()
            assert len(rows) == 2
            track_ids = {row[1][0] for row in rows}
            assert track_ids == {str(first_response.rounds[0].question.track_ids[0])}

            cursor.execute("SELECT count(*) FROM track WHERE id = %s", (str(track_ids.pop()),))
            (track_count,) = cursor.fetchone()
            assert track_count == 1

            cursor.execute(
                "SELECT count(*) FROM artist WHERE id = %s",
                (str(first_response.rounds[0].correct_artist_id),),
            )
            (artist_count,) = cursor.fetchone()
            assert artist_count == 1


def test_catalogue_repository_returns_the_stored_provider_title() -> None:
    with connection() as conn:
        _seed_eligible_artist(conn)
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM artist LIMIT 1")
            (artist_id,) = cursor.fetchone()

    with connection() as conn:
        tracks = CatalogueRepository(conn).get_tracks_for_artist(artist_id)

    assert len(tracks) == 1
    assert len(tracks[0].providers) == 1
    assert tracks[0].providers[0].title == "Test Track"
