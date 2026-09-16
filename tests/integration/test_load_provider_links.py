import json
import os
from uuid import uuid4

import pytest

from scripts.load_provider_links import load
from src.repositories.db import connection

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL is required for Postgres integration tests",
)


def test_migration_and_loader_populate_an_empty_registry(tmp_path) -> None:
    recording_id = uuid4()
    provider_url = f"https://example.test/{recording_id}/track.mp3"
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM catalogue.recording_provider WHERE provider_url = %s",
                (provider_url,),
            )

    source = tmp_path / "provider-links.json"
    source.write_text(
        json.dumps(
            {
                "recordings": [
                    {
                        "musicBrainzRecordingId": str(recording_id),
                        "sources": [
                            {
                                "provider": "archive.org",
                                "url": provider_url,
                                "durationMs": 180_000,
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    summary = load(source)

    assert summary.sources == 1
    assert summary.skipped == 0
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT musicbrainz_recording_id, provider, provider_url
                FROM catalogue.recording_provider
                WHERE provider_url = %s
                """,
                (provider_url,),
            )
            assert cursor.fetchone() == (
                recording_id,
                "archive.org",
                provider_url,
            )
