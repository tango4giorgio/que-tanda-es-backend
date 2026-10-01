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
    """Seed one artist with one playable track (data-model.md `artist`/`track`/
    `track_provider`)."""
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
            INSERT INTO track_provider (track_id, provider, provider_track_id, duration_ms)
            VALUES (%s, 'deezer', %s, 180000)
            """,
            (str(track_id), f"item-{uuid4().hex}"),
        )


def test_two_separately_created_games_reuse_the_same_track_and_artist_records() -> None:
    with connection() as conn:
        for _ in range(3):
            _seed_eligible_artist(conn)

    # A fixed random seed makes round selection deterministic across the two calls below,
    # given an unchanged catalogue: both games are expected to land on the same correct
    # artist/track (User Story 2 acceptance scenarios 1-2).
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

    assert first_response.game_id != second_response.game_id
    assert first_response.rounds[0].correct_artist_id == second_response.rounds[0].correct_artist_id
    first_track_id = first_response.rounds[0].question.track_ids[0]
    second_track_id = second_response.rounds[0].question.track_ids[0]
    assert first_track_id == second_track_id

    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM track WHERE id = %s", (str(first_track_id),)
            )
            (track_count,) = cursor.fetchone()
            assert track_count == 1

            cursor.execute(
                "SELECT count(*) FROM artist WHERE id = %s",
                (str(first_response.rounds[0].correct_artist_id),),
            )
            (artist_count,) = cursor.fetchone()
            assert artist_count == 1
