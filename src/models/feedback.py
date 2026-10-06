from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from src.models.entities import TimestampedEntity

FeedbackOutcome = Literal["correct", "incorrect", "skipped"]


class FeedbackSubmission(BaseModel):
    question_id: UUID = Field(validation_alias="questionId")
    track_position: int = Field(ge=1, le=3, validation_alias="trackPosition")
    guessed_artist_id: UUID | None = Field(validation_alias="guessedArtistId")
    outcome: FeedbackOutcome
    elapsed_ms: int = Field(ge=0, le=30_000, validation_alias="elapsedMs")

    @model_validator(mode="after")
    def validate_guessed_artist_pairing(self) -> "FeedbackSubmission":
        if self.outcome == "skipped" and self.guessed_artist_id is not None:
            raise ValueError("guessedArtistId must be null when outcome is 'skipped'")
        if self.outcome != "skipped" and self.guessed_artist_id is None:
            raise ValueError("guessedArtistId is required unless outcome is 'skipped'")
        return self


class GuessFeedback(TimestampedEntity):
    """The outcome of a player's response to one question (data-model.md `guess_feedback`)."""

    id: UUID
    question_id: UUID
    track_position: int
    guessed_artist_id: UUID | None
    outcome: FeedbackOutcome
    elapsed_ms: int
