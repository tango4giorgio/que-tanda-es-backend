from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class RoundRequest(BaseModel):
    excluded_artist_ids: frozenset[UUID] = frozenset()


class RoundChoice(BaseModel):
    artist_id: UUID = Field(serialization_alias="artistId")
    display_name: str = Field(min_length=1, serialization_alias="displayName")

    model_config = ConfigDict(populate_by_name=True)


class RoundTrack(BaseModel):
    recording_id: UUID = Field(serialization_alias="recordingId")
    provider: str = Field(min_length=1)
    preview_url: HttpUrl = Field(serialization_alias="previewUrl")
    duration_ms: int | None = Field(default=None, gt=0, serialization_alias="durationMs")


class RoundResponse(BaseModel):
    correct_artist_id: UUID = Field(serialization_alias="correctArtistId")
    round_token: str = Field(min_length=1, serialization_alias="roundToken")
    choices: list[RoundChoice]
    tracks: list[RoundTrack]

    @model_validator(mode="after")
    def validate_round(self) -> "RoundResponse":
        if len(self.choices) != 3 or len({choice.artist_id for choice in self.choices}) != 3:
            raise ValueError("a round must contain three distinct choices")
        choice_ids = {choice.artist_id for choice in self.choices}
        if self.correct_artist_id not in choice_ids:
            raise ValueError("the correct artist must be one of the choices")
        if not 1 <= len(self.tracks) <= 3:
            raise ValueError("a round must contain between one and three tracks")
        if len({track.recording_id for track in self.tracks}) != len(self.tracks):
            raise ValueError("a round must contain distinct recordings")
        return self


class RoundUnavailableError(RuntimeError):
    """Raised when eligible content cannot form a complete round."""
