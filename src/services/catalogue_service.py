import hashlib
import json

from src.models.catalogue import CatalogueResponse
from src.repositories.catalogue_repository import CatalogueRepository


class CatalogueService:
    def __init__(self, repository: CatalogueRepository):
        self.repository = repository

    def get_catalogue(self) -> CatalogueResponse:
        orchestras, tracks = self.repository.get_usable_catalogue()
        version_payload = {
            "orchestras": orchestras,
            "tracks": [track.model_dump(mode="json") for track in tracks],
        }
        version = hashlib.sha256(
            json.dumps(version_payload, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]
        return CatalogueResponse.from_entries(orchestras, tracks, version)

    def get_track_canonical_links(self, track_id: str) -> dict[str, str | None] | None:
        return self.repository.get_track_entry_with_canonical_links(track_id)
