from src.models.track_entry import CatalogueTrackEntry


def test_canonical_recording_link_is_optional() -> None:
    without_link = CatalogueTrackEntry(
        id="track-1",
        orchestra_id="orchestra",
        title="Track",
        preview_url="https://example.test/track.mp3",
        duration_ms=120_000,
    )
    with_link = without_link.model_copy(update={"recording_id": "recording-1"})

    assert without_link.recording_id is None
    assert with_link.recording_id == "recording-1"
