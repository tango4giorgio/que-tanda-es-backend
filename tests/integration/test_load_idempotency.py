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


def test_repeated_load_does_not_create_duplicate_provider_links(tmp_path) -> None:
    recording_id = uuid4()
    provider_url = f"https://example.test/{recording_id}/track.mp3"
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

    first_summary = load(source)
    second_summary = load(source)

    assert first_summary.sources == 1
    assert second_summary.sources == 1
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT count(*)
                FROM catalogue.recording_provider
                WHERE provider_url = %s
                """,
                (provider_url,),
            )
            assert cursor.fetchone()[0] == 1
