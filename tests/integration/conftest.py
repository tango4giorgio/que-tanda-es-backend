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
        Path(__file__).parents[2] / "src" / "migrations" / "0001_create_catalogue_schema.sql"
        ),
        (
            Path(__file__).parents[2]
            / "src"
            / "migrations"
            / "0002_create_musicbrainz_recording_cache.sql"
        ),
        (
            Path(__file__).parents[2]
            / "src"
            / "migrations"
            / "0003_create_feedback_schema.sql"
        ),
    ]
    with psycopg.connect(database_url, prepare_threshold=None) as conn:
        for migration in migrations:
            conn.execute(migration.read_text(encoding="utf-8"))
