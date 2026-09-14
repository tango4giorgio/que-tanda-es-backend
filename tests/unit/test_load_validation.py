from src.models.track_entry import CatalogueTrackEntry


def test_invalid_source_row_can_be_reported_without_stopping_load() -> None:
    try:
        CatalogueTrackEntry(
            id="track",
            orchestra_id="orchestra",
            title="Title",
            preview_url="",
            duration_ms=120_000,
        )
    except ValueError as error:
        assert "preview_url" in str(error)
    else:
        raise AssertionError("Expected blank preview URL to be rejected")
