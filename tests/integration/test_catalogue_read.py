import os
from uuid import uuid4

import pytest

from src.models.provider_source import ProviderSource
from src.repositories.catalogue_repository import CatalogueRepository
from src.repositories.db import connection

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL is required for Postgres integration tests",
)


def test_catalogue_repository_reads_only_usable_provider_sources() -> None:
    with connection() as conn:
        recording_id = uuid4()
        repository = CatalogueRepository(conn)
        repository.upsert_source(
            ProviderSource(
                musicbrainz_recording_id=recording_id,
                provider="archive.org",
                provider_url=f"https://example.test/{recording_id}/one.mp3",
                duration_ms=120_000,
            )
        )
        repository.upsert_source(
            ProviderSource(
                musicbrainz_recording_id=recording_id,
                provider="deezer",
                provider_url=f"https://example.test/{recording_id}/two.mp3",
                duration_ms=None,
            )
        )
        repository.upsert_source(
            ProviderSource(
                musicbrainz_recording_id=uuid4(),
                provider="archive.org",
                provider_url=f"https://example.test/{recording_id}/short.mp3",
                duration_ms=10_000,
            )
        )
        repository.commit()
        sources = repository.get_usable_sources()

    matching_sources = [
        source for source in sources if source.musicbrainz_recording_id == recording_id
    ]
    assert [source.provider for source in matching_sources] == ["archive.org", "deezer"]
    assert all(source.is_usable for source in matching_sources)
