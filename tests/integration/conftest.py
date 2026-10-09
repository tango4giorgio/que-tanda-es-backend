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
        Path(__file__).parents[2] / "src" / "migrations" / "0001_create_schema.sql",
        Path(__file__).parents[2] / "src" / "migrations" / "0002_seed_catalogue.sql",
        Path(__file__).parents[2] / "src" / "migrations" / "0003_create_session_schema.sql",
        Path(__file__).parents[2]
        / "src"
        / "migrations"
        / "0004_add_session_id_to_guess_feedback.sql",
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
            "track_provider, track, artist, session RESTART IDENTITY CASCADE"
        )
