from unittest.mock import Mock
from uuid import UUID

from src.models.provider_source import ProviderSource
from src.services.catalogue_service import CatalogueService


def test_catalogue_service_groups_and_orders_sources_by_musicbrainz_recording() -> None:
    repository = Mock()
    first_recording_id = UUID("1a5d9d31-64a7-4a5d-87bd-1934d7efbb84")
    second_recording_id = UUID("5a5d9d31-64a7-4a5d-87bd-1934d7efbb84")
    repository.get_usable_sources.return_value = [
        ProviderSource(
            musicbrainz_recording_id=second_recording_id,
            provider="deezer",
            provider_url="https://example.test/deezer-preview.mp3",
            duration_ms=120_000,
        ),
        ProviderSource(
            musicbrainz_recording_id=second_recording_id,
            provider="archive.org",
            provider_url="https://archive.org/download/example/track.mp3",
            duration_ms=None,
        ),
        ProviderSource(
            musicbrainz_recording_id=first_recording_id,
            provider="archive.org",
            provider_url="https://archive.org/download/example/first.mp3",
            duration_ms=180_000,
        ),
    ]

    response = CatalogueService(repository).get_provider_links()

    assert [recording["recordingId"] for recording in response] == [
        str(first_recording_id),
        str(second_recording_id),
    ]
    assert [link["provider"] for link in response[1]["links"]] == ["archive.org", "deezer"]
