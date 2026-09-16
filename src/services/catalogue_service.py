from collections import defaultdict

from src.repositories.catalogue_repository import CatalogueRepository


class CatalogueService:
    def __init__(self, repository: CatalogueRepository):
        self.repository = repository

    def get_provider_links(self) -> list[dict[str, object]]:
        grouped: dict[str, list[dict[str, str | int | None]]] = defaultdict(list)
        for source in self.repository.get_usable_sources():
            grouped[str(source.musicbrainz_recording_id)].append(
                {
                    "provider": source.provider,
                    "url": str(source.provider_url),
                    "durationMs": source.duration_ms,
                }
            )
        return [
            {
                "recordingId": recording_id,
                "links": sorted(links, key=lambda link: (str(link["provider"]), str(link["url"]))),
            }
            for recording_id, links in sorted(grouped.items())
        ]
