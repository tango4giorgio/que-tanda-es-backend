from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

FeedbackOutcome = Literal["correct", "wrong", "skipped"]


class FeedbackSubmission(BaseModel):
    round_token: str = Field(min_length=1, validation_alias="roundToken")
    track_position: int = Field(ge=1, le=3, validation_alias="trackPosition")
    recording_id: UUID = Field(validation_alias="recordingId")
    correct_artist_id: UUID = Field(validation_alias="correctArtistId")
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
