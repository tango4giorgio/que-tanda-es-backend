import os
from uuid import uuid4

import psycopg
import pytest

from src.models.provider_source import ProviderSource
from src.repositories.catalogue_repository import CatalogueRepository
from src.repositories.db import connection

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL is required for Postgres integration tests",
)


def test_provider_url_cannot_reference_conflicting_recordings() -> None:
    provider_url = f"https://example.test/{uuid4()}/track.mp3"
    with connection() as conn:
        repository = CatalogueRepository(conn)
        repository.upsert_source(
            ProviderSource(
                musicbrainz_recording_id=uuid4(),
                provider="archive.org",
                provider_url=provider_url,
            )
        )
        repository.commit()

        with pytest.raises(psycopg.errors.UniqueViolation):
            repository.upsert_source(
                ProviderSource(
                    musicbrainz_recording_id=uuid4(),
                    provider="archive.org",
                    provider_url=provider_url,
                )
            )
        conn.rollback()
