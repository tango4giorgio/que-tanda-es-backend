from uuid import UUID

from src.models.provider_source import ProviderSource

RECORDING_ID = UUID("5a5d9d31-64a7-4a5d-87bd-1934d7efbb84")


def test_recording_can_have_multiple_provider_sources() -> None:
    sources = [
        ProviderSource(
            musicbrainz_recording_id=RECORDING_ID,
            provider="archive.org",
            provider_url="https://archive.org/download/example/track.mp3",
        ),
        ProviderSource(
            musicbrainz_recording_id=RECORDING_ID,
            provider="deezer",
            provider_url="https://example.test/deezer-preview.mp3",
        ),
    ]

    assert {source.provider for source in sources} == {"archive.org", "deezer"}
    assert {source.musicbrainz_recording_id for source in sources} == {RECORDING_ID}
