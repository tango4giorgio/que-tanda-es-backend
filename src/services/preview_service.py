from uuid import UUID

from src.config import deployed_environment
from src.models.round import PreviewResponse, TrackPreview, TrackPreviewNotFoundError
from src.repositories.catalogue_repository import CatalogueRepository
from src.services.provider_url_resolver import UnknownProviderError, resolve_preview_url


class PreviewService:
    def __init__(
        self, catalogue_repository: CatalogueRepository, deployed: bool | None = None
    ):
        self.catalogue_repository = catalogue_repository
        self.deployed = deployed_environment() if deployed is None else deployed

    def get_previews(self, track_ids: list[UUID]) -> PreviewResponse:
        providers_by_track = self.catalogue_repository.get_providers_for_tracks(track_ids)
        previews: list[TrackPreview] = []
        missing: list[UUID] = []
        for track_id in track_ids:
            preview = None
            for provider in providers_by_track.get(track_id, []):
                try:
                    preview_url = resolve_preview_url(
                        provider.provider, provider.provider_track_id
                    )
                except UnknownProviderError:
                    continue
                if self.deployed and not preview_url.startswith("https://"):
                    continue
                preview = TrackPreview(
                    track_id=track_id,
                    provider=provider.provider,
                    preview_url=preview_url,
                    duration_ms=provider.duration_ms,
                )
                break
            if preview is None:
                missing.append(track_id)
            else:
                previews.append(preview)
        if missing:
            raise TrackPreviewNotFoundError(missing)
        return PreviewResponse(previews=previews)
