from collections import defaultdict
from collections.abc import Callable, Sequence
from random import Random
from uuid import UUID, uuid4

from src.config import deployed_environment
from src.models.round import (
    RoundChoice,
    RoundRequest,
    RoundResponse,
    RoundTrack,
    RoundUnavailableError,
)
from src.repositories.round_repository import RoundRepository

# Bound how many correct-artist candidates we probe for a playable recording
# before giving up. This keeps worst-case query volume small even when a
# large fraction of artists happen to lack a deployment-eligible preview.
MAX_CORRECT_ARTIST_ATTEMPTS = 20


class RoundService:
    def __init__(
        self,
        repository: RoundRepository,
        random_source: Random | Callable[[Sequence[object]], object] | None = None,
        deployed: bool | None = None,
    ):
        self.repository = repository
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

    def create_round(self, request: RoundRequest) -> RoundResponse:
        artists = self.repository.get_eligible_artists(request.excluded_artist_ids)
        if len({artist.artist_id for artist in artists}) < 3:
            raise RoundUnavailableError

        names = {artist.artist_id: artist.artist_name for artist in artists}
        remaining_candidates = self._choose(list(names), len(names))

        correct_id: UUID | None = None
        tracks: list[RoundTrack] = []
        for candidate_id in remaining_candidates[:MAX_CORRECT_ARTIST_ATTEMPTS]:
            recordings = self.repository.get_playable_recordings_for_artist(candidate_id)
            by_recording = defaultdict(list)
            for recording in recordings:
                if self.deployed and str(recording.source.provider_url).startswith("http://"):
                    continue
                by_recording[recording.recording_id].append(recording)
            if not by_recording:
                continue
            correct_id = candidate_id
            selected_recordings = self._choose(list(by_recording), min(3, len(by_recording)))
            for recording_id in selected_recordings:
                source = self._choose(by_recording[recording_id], 1)[0].source
                tracks.append(
                    RoundTrack(
                        recording_id=recording_id,
                        provider=source.provider,
                        preview_url=source.provider_url,
                        duration_ms=source.duration_ms,
                    )
                )
            break

        if correct_id is None:
            raise RoundUnavailableError

        other_ids = [artist_id for artist_id in names if artist_id != correct_id]
        if len(other_ids) < 2:
            raise RoundUnavailableError
        distractor_ids = self._choose(other_ids, 2)
        choice_ids = self._choose([correct_id, *distractor_ids], 3)

        return RoundResponse(
            correct_artist_id=correct_id,
            # Fresh per round, opaque, and never persisted here; it exists only so the
            # client can tag its feedback submissions for this round (see feature 014).
            round_token=uuid4().hex,
            choices=[
                RoundChoice(artist_id=artist_id, display_name=names[artist_id])
                for artist_id in choice_ids
            ],
            tracks=tracks,
        )
