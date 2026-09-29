from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from src.models.round import TrackPreviewNotFoundError
from src.models.track import TrackProvider
from src.services.preview_service import PreviewService

NOW = datetime.now(UTC)
TRACK_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def provider(name: str, provider_track_id: str) -> TrackProvider:
    return TrackProvider(
        id=uuid4(),
        track_id=TRACK_ID,
        provider=name,
        provider_track_id=provider_track_id,
        duration_ms=30_000,
        created_at=NOW,
        updated_at=NOW,
    )


class FakeCatalogueRepository:
    def __init__(self, providers):
        self.providers = providers

    def get_providers_for_tracks(self, track_ids):
        return {track_id: self.providers.get(track_id, []) for track_id in track_ids}


def test_resolves_one_preview_per_track_in_request_order() -> None:
    second_track_id = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    repository = FakeCatalogueRepository(
        {
            TRACK_ID: [provider("deezer", "123")],
            second_track_id: [
                TrackProvider(
                    id=uuid4(),
                    track_id=second_track_id,
                    provider="archive.org",
                    provider_track_id="item",
                    duration_ms=25_000,
                    created_at=NOW,
                    updated_at=NOW,
                )
            ],
        }
    )

    response = PreviewService(repository, deployed=False).get_previews(
        [second_track_id, TRACK_ID]
    )

    assert [preview.track_id for preview in response.previews] == [second_track_id, TRACK_ID]
    assert response.previews[1].preview_url == "https://www.deezer.com/track/123"


def test_skips_unsupported_provider_and_uses_supported_fallback() -> None:
    repository = FakeCatalogueRepository(
        {TRACK_ID: [provider("unknown", "bad"), provider("deezer", "123")]}
    )

    response = PreviewService(repository, deployed=False).get_previews([TRACK_ID])

    assert response.previews[0].provider == "deezer"


def test_missing_preview_fails_the_batch() -> None:
    with pytest.raises(TrackPreviewNotFoundError) as error:
        PreviewService(FakeCatalogueRepository({}), deployed=False).get_previews([TRACK_ID])

    assert error.value.track_ids == [TRACK_ID]
