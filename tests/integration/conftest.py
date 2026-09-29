import os
from pathlib import Path

import psycopg
import pytest


@pytest.fixture(scope="session", autouse=True)
def apply_catalogue_migration() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return

    migrations = [
        (
            Path(__file__).parents[2] / "src" / "migrations" / "0001_create_game_schema.sql"
        ),
        (
            Path(__file__).parents[2]
            / "src"
            / "migrations"
            / "0002_create_catalogue_entities.sql"
        ),
        (
            Path(__file__).parents[2]
            / "src"
            / "migrations"
            / "0003_create_question_and_feedback.sql"
        ),
        (Path(__file__).parents[2] / "src" / "migrations" / "0004_seed_artists.sql"),
        (
            Path(__file__).parents[2]
            / "src"
            / "migrations"
            / "0005_seed_deezer_tracks.sql"
        ),
        (
            Path(__file__).parents[2]
            / "src"
            / "migrations"
            / "0006_rebuild_gameplay_question_model.sql"
        ),
        (
            Path(__file__).parents[2]
            / "src"
            / "migrations"
            / "0007_create_question_functions.sql"
        ),
        (
            Path(__file__).parents[2]
            / "src"
            / "migrations"
            / "0008_create_admin_question_view.sql"
        ),
        (
            Path(__file__).parents[2]
            / "src"
            / "migrations"
            / "0009_create_game_round_question_links.sql"
        ),
    ]
    with psycopg.connect(database_url, prepare_threshold=None) as conn:
        for migration in migrations:
            conn.execute(migration.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _reset_schema_between_tests() -> None:
    """Game selection reads across the entire catalogue, so data left over from a previous
    test would make outcomes non-deterministic. Truncate every table before each test."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return
    with psycopg.connect(database_url, prepare_threshold=None) as conn:
        conn.execute(
            "TRUNCATE guess_feedback, round_question, game_round, round, question, game, "
            "track_provider, track, artist RESTART IDENTITY CASCADE"
        )
