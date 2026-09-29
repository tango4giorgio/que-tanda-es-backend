from datetime import UTC, datetime
from uuid import uuid4

from src.models.track import Track, TrackProvider

ARTIST_ID = uuid4()
TRACK_ID = uuid4()
NOW = datetime.now(UTC)


def _provider(provider: str, provider_track_id: str) -> TrackProvider:
    return TrackProvider(
        id=uuid4(),
        track_id=TRACK_ID,
        provider=provider,
        provider_track_id=provider_track_id,
        created_at=NOW,
        updated_at=NOW,
    )


def test_a_track_can_have_multiple_track_provider_rows() -> None:
    track = Track(id=TRACK_ID, artist_id=ARTIST_ID, created_at=NOW, updated_at=NOW)
    providers = [
        _provider("archive.org", "example"),
        _provider("deezer", "123456"),
    ]

    assert {provider.provider for provider in providers} == {"archive.org", "deezer"}
    assert {provider.track_id for provider in providers} == {track.id}
