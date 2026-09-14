from unittest.mock import Mock

from src.models.track_entry import CatalogueTrackEntry
from src.services.catalogue_service import CatalogueService


def test_catalogue_service_assembles_frontend_response() -> None:
    repository = Mock()
    repository.get_usable_catalogue.return_value = (
        [("di-sarli", "Carlos Di Sarli")],
        [
            CatalogueTrackEntry(
                id="di-sarli.track-0",
                orchestra_id="di-sarli",
                title="Track",
                preview_url="https://example.test/track.mp3",
                duration_ms=120_000,
            )
        ],
    )

    response = CatalogueService(repository).get_catalogue().model_dump(by_alias=True)

    assert response["orchestras"] == [{"id": "di-sarli", "displayName": "Carlos Di Sarli"}]
    assert response["tracks"][0]["previewUrl"] == "https://example.test/track.mp3"
