from collections import defaultdict
from random import Random
from uuid import UUID

from src.models.provider_source import ProviderSource
from src.models.round import RoundRequest
from src.repositories.round_repository import EligibleArtist, PlayableRecording
from src.services.round_service import RoundService


def recording(recording_id: str, artist_id: str, artist_name: str) -> PlayableRecording:
    return PlayableRecording(
        recording_id=UUID(recording_id),
        artist_id=UUID(artist_id),
        artist_name=artist_name,
        source=ProviderSource(
            musicbrainz_recording_id=UUID(recording_id),
            provider="archive.org",
            provider_url=f"https://example.test/{recording_id}.mp3",
            duration_ms=120_000,
        ),
    )


class FakeRoundRepository:
    """A stand-in for RoundRepository that serves eligible artists and
    per-artist recordings from an in-memory fixture, mirroring the narrowed
    query shape the real repository exposes."""

    def __init__(self, rows: list[PlayableRecording]):
        self.rows = rows

    def get_eligible_artists(self, excluded: frozenset[UUID]) -> list[EligibleArtist]:
        seen: dict[UUID, str] = {}
        for row in self.rows:
            if row.artist_id in excluded:
                continue
            seen[row.artist_id] = row.artist_name
        return [EligibleArtist(artist_id=aid, artist_name=name) for aid, name in seen.items()]

    def get_playable_recordings_for_artist(self, artist_id: UUID) -> list[PlayableRecording]:
        return [row for row in self.rows if row.artist_id == artist_id]


def sample_rows() -> list[PlayableRecording]:
    return [
        recording(
            "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "11111111-1111-1111-1111-111111111111",
            "A",
        ),
        recording(
            "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "11111111-1111-1111-1111-111111111111",
            "A",
        ),
        recording(
            "cccccccc-cccc-cccc-cccc-cccccccccccc",
            "22222222-2222-2222-2222-222222222222",
            "B",
        ),
        recording(
            "dddddddd-dddd-dddd-dddd-dddddddddddd",
            "33333333-3333-3333-3333-333333333333",
            "C",
        ),
        recording(
            "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
            "44444444-4444-4444-4444-444444444444",
            "D",
        ),
    ]


def test_round_selects_three_artists_and_one_provider_per_recording() -> None:
    repository = FakeRoundRepository(sample_rows())

    result = RoundService(repository, random_source=Random(4)).create_round(RoundRequest())

    assert len(result.choices) == 3
    assert len({choice.artist_id for choice in result.choices}) == 3
    assert 1 <= len(result.tracks) <= 3
    assert len({track.recording_id for track in result.tracks}) == len(result.tracks)
    assert result.correct_artist_id in {choice.artist_id for choice in result.choices}


def test_round_excludes_requested_artists_everywhere() -> None:
    repository = FakeRoundRepository(sample_rows())
    excluded = frozenset({UUID("11111111-1111-1111-1111-111111111111")})

    result = RoundService(repository, random_source=Random(1)).create_round(
        RoundRequest(excluded_artist_ids=excluded)
    )

    all_artist_ids = {choice.artist_id for choice in result.choices}
    assert UUID("11111111-1111-1111-1111-111111111111") not in all_artist_ids
    assert result.correct_artist_id != UUID("11111111-1111-1111-1111-111111111111")


def test_round_selects_one_provider_per_recording_when_multiple_exist() -> None:
    rows = sample_rows()
    duplicate = recording(
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "11111111-1111-1111-1111-111111111111",
        "A",
    )
    duplicate = duplicate.__class__(
        recording_id=duplicate.recording_id,
        artist_id=duplicate.artist_id,
        artist_name=duplicate.artist_name,
        source=ProviderSource(
            musicbrainz_recording_id=duplicate.recording_id,
            provider="deezer",
            provider_url="https://example.test/alternate.mp3",
            duration_ms=150_000,
        ),
    )
    repository = FakeRoundRepository([*rows, duplicate])

    result = RoundService(repository, random_source=Random(4)).create_round(RoundRequest())

    providers_by_recording = defaultdict(set)
    for track in result.tracks:
        providers_by_recording[track.recording_id].add(track.provider)
    assert all(len(providers) == 1 for providers in providers_by_recording.values())
