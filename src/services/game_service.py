from collections.abc import Callable, Sequence
from random import Random
from uuid import UUID

from psycopg import Connection

from src.config import deployed_environment
from src.models.round import (
    GameChoice,
    GameQuestion,
    GameRequest,
    GameResponse,
    GameRound,
    GameUnavailableError,
)
from src.repositories.catalogue_repository import CatalogueRepository, TrackWithProviders
from src.repositories.game_repository import GameRepository
from src.services.provider_url_resolver import resolve_preview_url, supports_preview_provider

MAX_CORRECT_ARTIST_ATTEMPTS = 20


class GameService:
    def __init__(
        self,
        catalogue_repository: CatalogueRepository,
        game_repository: GameRepository,
        conn: Connection,
        random_source: Random | Callable[[Sequence[object]], object] | None = None,
        deployed: bool | None = None,
    ):
        self.catalogue_repository = catalogue_repository
        self.game_repository = game_repository
        self.conn = conn
        self.random_source = random_source or Random()
        self.deployed = deployed_environment() if deployed is None else deployed

    def _choose(self, values: Sequence[object], count: int) -> list[object]:
        if hasattr(self.random_source, "sample"):
            return list(self.random_source.sample(list(values), count))  # type: ignore[attr-defined]
        chooser = self.random_source
        remaining = list(values)
        chosen = []
        for _ in range(count):
            selected = chooser(remaining)
            chosen.append(selected)
            remaining.remove(selected)
        return chosen

    def _has_playable_provider(self, entry: TrackWithProviders) -> bool:
        for provider in entry.providers:
            if not supports_preview_provider(provider.provider):
                continue
            preview_url = resolve_preview_url(provider.provider, provider.provider_track_id)
            if not self.deployed or preview_url.startswith("https://"):
                return True
        return False

    def create_game(self, request: GameRequest) -> GameResponse:
        artists = self.catalogue_repository.get_eligible_artists(request.excluded_artist_ids)
        names = {artist.id: artist.display_name for artist in artists}
        if len(names) < 3:
            raise GameUnavailableError

        playable_rounds: list[tuple[UUID, list[TrackWithProviders]]] = []
        candidates = self._choose(list(names), len(names))
        for candidate_id in candidates[:MAX_CORRECT_ARTIST_ATTEMPTS]:
            tracks = [
                entry
                for entry in self.catalogue_repository.get_tracks_for_artist(candidate_id)
                if self._has_playable_provider(entry)
            ]
            if tracks:
                playable_rounds.append(
                    (candidate_id, self._choose(tracks, min(3, len(tracks))))
                )
            if len(playable_rounds) == 3:
                break
        if len(playable_rounds) != 3:
            raise GameUnavailableError

        game_id = self.game_repository.create_game()
        rounds: list[GameRound] = []
        for correct_id, selected_tracks in playable_rounds:
            distractor_ids = self._choose(
                [artist_id for artist_id in names if artist_id != correct_id], 2
            )
            choice_ids = self._choose([correct_id, *distractor_ids], 3)
            track_ids = [entry.track.id for entry in selected_tracks]
            question_id = self.game_repository.create_question(track_ids, choice_ids)
            round_id, sequence_number = self.game_repository.append_round(
                game_id, question_id
            )
            rounds.append(
                GameRound(
                    round_id=round_id,
                    sequence_number=sequence_number,
                    correct_artist_id=correct_id,
                    choices=[
                        GameChoice(artist_id=artist_id, display_name=names[artist_id])
                        for artist_id in choice_ids
                    ],
                    question=GameQuestion(
                        question_id=question_id,
                        track_ids=track_ids,
                    ),
                )
            )
        return GameResponse(game_id=game_id, rounds=rounds)
