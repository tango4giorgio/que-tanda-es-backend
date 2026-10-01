from datetime import UTC, datetime
from random import Random
from uuid import UUID, uuid4

import pytest

from src.models.round import GameRequest, GameUnavailableError
from src.models.track import Artist, Track, TrackProvider
from src.repositories.catalogue_repository import TrackWithProviders
from src.services.game_service import GameService

FIXED_TIME = datetime(2024, 1, 1, tzinfo=UTC)


def artist(artist_id: str, display_name: str) -> Artist:
    return Artist(
        id=UUID(artist_id),
        display_name=display_name,
        created_at=FIXED_TIME,
        updated_at=FIXED_TIME,
    )


def track_with_provider(track_id: str, artist_id: str) -> TrackWithProviders:
    return TrackWithProviders(
        track=Track(
            id=UUID(track_id),
            artist_id=UUID(artist_id),
            created_at=FIXED_TIME,
            updated_at=FIXED_TIME,
        ),
        providers=[
            TrackProvider(
                id=uuid4(),
                track_id=UUID(track_id),
                provider="deezer",
                provider_track_id=track_id,
                duration_ms=120_000,
                created_at=FIXED_TIME,
                updated_at=FIXED_TIME,
            )
        ],
    )


class FakeCatalogueRepository:
    def __init__(
        self,
        artists: list[Artist],
        tracks_by_artist: dict[UUID, list[TrackWithProviders]],
    ):
        self.artists = artists
        self.tracks_by_artist = tracks_by_artist

    def get_eligible_artists(
        self, excluded_artist_ids: frozenset[UUID] = frozenset()
    ) -> list[Artist]:
        return [artist_ for artist_ in self.artists if artist_.id not in excluded_artist_ids]

    def get_tracks_for_artist(self, artist_id: UUID) -> list[TrackWithProviders]:
        return self.tracks_by_artist.get(artist_id, [])


class FakeGameRepository:
    def __init__(self) -> None:
        self.game_id = uuid4()
        self.round_count = 0
        self.links: list[tuple[UUID, UUID, UUID, int]] = []

    def create_game(self) -> UUID:
        return self.game_id

    def create_question(self, track_ids: list[UUID], artist_ids: list[UUID]) -> UUID:
        assert 1 <= len(track_ids) <= 3
        assert len(artist_ids) == 3
        return uuid4()

    def append_round(self, game_id: UUID, question_id: UUID) -> tuple[UUID, int]:
        assert game_id == self.game_id
        assert question_id is not None
        self.round_count += 1
        round_id = uuid4()
        self.links.append((game_id, round_id, question_id, self.round_count))
        return round_id, self.round_count


class FakeCursor:
    def __enter__(self) -> "FakeCursor":
        self._question_id: UUID | None = None
        return self

    def __exit__(self, *args: object) -> bool:
        return False

    def execute(self, query: str, params: object = None) -> None:
        if query.strip().startswith("INSERT INTO question ("):
            self._question_id = uuid4()

    def fetchone(self) -> tuple[UUID]:
        return (self._question_id,)


class FakeConnection:
    def cursor(self) -> FakeCursor:
        return FakeCursor()


def sample_fixture() -> tuple[list[Artist], dict[UUID, list[TrackWithProviders]]]:
    artists = [
        artist("11111111-1111-1111-1111-111111111111", "A"),
        artist("22222222-2222-2222-2222-222222222222", "B"),
        artist("33333333-3333-3333-3333-333333333333", "C"),
        artist("44444444-4444-4444-4444-444444444444", "D"),
    ]
    tracks_by_artist = {
        artist_.id: [
            track_with_provider(
                f"{index}{index}{index}{index}{index}{index}{index}{index}-"
                f"{index}{index}{index}{index}-"
                f"{index}{index}{index}{index}-"
                f"{index}{index}{index}{index}-"
                f"{index}{index}{index}{index}{index}{index}{index}{index}{index}{index}{index}{index}",
                str(artist_.id),
            )
        ]
        for index, artist_ in enumerate(artists, start=1)
    }
    return artists, tracks_by_artist


def make_service(random_source: Random | None = None) -> GameService:
    artists, tracks_by_artist = sample_fixture()
    return GameService(
        FakeCatalogueRepository(artists, tracks_by_artist),
        FakeGameRepository(),
        FakeConnection(),
        random_source=random_source,
        deployed=False,
    )


def test_game_contains_three_rounds_with_distinct_correct_artists() -> None:
    result = make_service(Random(4)).create_game(GameRequest())

    assert [round_.sequence_number for round_ in result.rounds] == [1, 2, 3]
    assert len({round_.correct_artist_id for round_ in result.rounds}) == 3
    assert all(len(round_.choices) == 3 for round_ in result.rounds)
    assert all(len(round_.question.track_ids) == 1 for round_ in result.rounds)


def test_game_excludes_requested_artists() -> None:
    excluded = UUID("11111111-1111-1111-1111-111111111111")

    result = make_service(Random(1)).create_game(
        GameRequest(excluded_artist_ids=frozenset({excluded}))
    )

    assert excluded not in {round_.correct_artist_id for round_ in result.rounds}


def test_game_requires_three_playable_artists() -> None:
    artists, tracks_by_artist = sample_fixture()
    tracks_by_artist[artists[0].id] = []
    tracks_by_artist[artists[1].id] = []
    service = GameService(
        FakeCatalogueRepository(artists, tracks_by_artist),
        FakeGameRepository(),
        FakeConnection(),
        random_source=Random(1),
        deployed=False,
    )

    with pytest.raises(GameUnavailableError):
        service.create_game(GameRequest())
