from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class GameRequest(BaseModel):
    excluded_artist_ids: frozenset[UUID] = frozenset()


class GameChoice(BaseModel):
    artist_id: UUID = Field(serialization_alias="artistId")
    display_name: str = Field(min_length=1, serialization_alias="displayName")

    model_config = ConfigDict(populate_by_name=True)


class GameQuestion(BaseModel):
    question_id: UUID = Field(serialization_alias="questionId")
    track_ids: list[UUID] = Field(
        min_length=1, max_length=3, serialization_alias="trackIds"
    )

    model_config = ConfigDict(populate_by_name=True)


class GameRound(BaseModel):
    round_id: UUID = Field(serialization_alias="roundId")
    sequence_number: int = Field(ge=1, le=3, serialization_alias="sequenceNumber")
    correct_artist_id: UUID = Field(serialization_alias="correctArtistId")
    choices: list[GameChoice]
    question: GameQuestion

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def validate_round(self) -> "GameRound":
        if len(self.choices) != 3 or len({choice.artist_id for choice in self.choices}) != 3:
            raise ValueError("a round must contain three distinct choices")
        if self.correct_artist_id not in {choice.artist_id for choice in self.choices}:
            raise ValueError("the correct artist must be one of the choices")
        if len(set(self.question.track_ids)) != len(self.question.track_ids):
            raise ValueError("a question must contain distinct tracks")
        return self


class GameResponse(BaseModel):
    game_id: UUID = Field(serialization_alias="gameId")
    rounds: list[GameRound]

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def validate_game(self) -> "GameResponse":
        if len(self.rounds) != 3:
            raise ValueError("a game must contain exactly three rounds")
        if {round_.sequence_number for round_ in self.rounds} != {1, 2, 3}:
            raise ValueError("a game must contain round sequence numbers 1, 2, and 3")
        if len({round_.correct_artist_id for round_ in self.rounds}) != 3:
            raise ValueError("a game must use three distinct correct artists")
        return self


class PreviewRequest(BaseModel):
    track_ids: list[UUID] = Field(min_length=1, validation_alias="trackIds")

    @field_validator("track_ids")
    @classmethod
    def deduplicate_track_ids(cls, values: list[UUID]) -> list[UUID]:
        unique_values = list(dict.fromkeys(values))
        if len(unique_values) > 50:
            raise ValueError("trackIds must contain at most 50 unique identifiers")
        return unique_values


class TrackPreview(BaseModel):
    track_id: UUID = Field(serialization_alias="trackId")
    provider: str = Field(min_length=1)
    preview_url: str = Field(min_length=1, serialization_alias="previewUrl")
    duration_ms: int | None = Field(default=None, gt=0, serialization_alias="durationMs")

    model_config = ConfigDict(populate_by_name=True)


class PreviewResponse(BaseModel):
    previews: list[TrackPreview]


class GameUnavailableError(RuntimeError):
    """Raised when eligible catalogue content cannot form a complete game."""


class TrackPreviewNotFoundError(RuntimeError):
    def __init__(self, track_ids: list[UUID]):
        self.track_ids = track_ids
        super().__init__("No playable preview exists for one or more requested tracks")
