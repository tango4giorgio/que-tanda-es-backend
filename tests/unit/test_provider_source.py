from uuid import UUID

import pytest
from pydantic import ValidationError

from src.models.provider_source import (
    MAX_DURATION_MS,
    MIN_DURATION_MS,
    ProviderSource,
    is_usable_source,
)

RECORDING_ID = UUID("5a5d9d31-64a7-4a5d-87bd-1934d7efbb84")


def test_usable_source_requires_url_and_valid_optional_duration() -> None:
    assert is_usable_source("https://example.test/track.mp3", None)
    assert is_usable_source("https://example.test/track.mp3", MIN_DURATION_MS)
    assert is_usable_source("https://example.test/track.mp3", MAX_DURATION_MS)
    assert not is_usable_source("https://example.test/track.mp3", MIN_DURATION_MS - 1)
    assert not is_usable_source("", MIN_DURATION_MS)


def test_provider_source_requires_musicbrainz_recording_and_provider() -> None:
    with pytest.raises(ValidationError):
        ProviderSource(
            musicbrainz_recording_id=RECORDING_ID,
            provider=" ",
            provider_url="https://example.test/track.mp3",
        )


def test_provider_source_requires_valid_url() -> None:
    with pytest.raises(ValidationError):
        ProviderSource(
            musicbrainz_recording_id=RECORDING_ID,
            provider="archive.org",
            provider_url="not-a-url",
        )


def test_provider_source_rejects_non_positive_duration() -> None:
    with pytest.raises(ValidationError):
        ProviderSource(
            musicbrainz_recording_id=RECORDING_ID,
            provider="archive.org",
            provider_url="https://example.test/track.mp3",
            duration_ms=0,
        )


def test_provider_source_marks_unknown_duration_usable() -> None:
    source = ProviderSource(
        musicbrainz_recording_id=RECORDING_ID,
        provider="archive.org",
        provider_url="https://example.test/track.mp3",
    )

    assert source.is_usable is True
