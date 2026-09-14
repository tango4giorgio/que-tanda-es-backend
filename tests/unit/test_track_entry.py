from src.models.track_entry import (
    MAX_DURATION_MS,
    MIN_DURATION_MS,
    CatalogueTrackEntry,
    is_usable_track,
)


def test_usable_track_requires_valid_duration_and_url() -> None:
    assert is_usable_track("https://example.test/track.mp3", MIN_DURATION_MS)
    assert is_usable_track("https://example.test/track.mp3", MAX_DURATION_MS)
    assert not is_usable_track("https://example.test/track.mp3", MIN_DURATION_MS - 1)
    assert not is_usable_track("", MIN_DURATION_MS)


def test_track_entry_rejects_non_positive_duration() -> None:
    try:
        CatalogueTrackEntry(
            id="track",
            orchestra_id="orchestra",
            title="Title",
            preview_url="https://example.test/track.mp3",
            duration_ms=0,
        )
    except ValueError as error:
        assert "greater than 0" in str(error)
    else:
        raise AssertionError("Expected invalid duration to be rejected")
