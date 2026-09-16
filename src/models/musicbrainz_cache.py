from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MetadataStatus(StrEnum):
    ELIGIBLE = "eligible"
    AMBIGUOUS_CREDIT = "ambiguous_credit"
    NOT_FOUND = "not_found"
    ERROR = "error"


class MusicBrainzCacheRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    musicbrainz_recording_id: UUID
    answer_artist_id: UUID | None = None
    answer_artist_name: str | None = None
    metadata_status: MetadataStatus
    source_updated_at: datetime | None = None
    fetched_at: datetime
    payload_hash: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_eligibility_fields(self) -> "MusicBrainzCacheRow":
        if self.metadata_status is MetadataStatus.ELIGIBLE and (
            self.answer_artist_id is None
            or self.answer_artist_name is None
            or not self.answer_artist_name.strip()
        ):
            raise ValueError("eligible cache rows require one artist identifier and name")
        return self


class RefreshResult(BaseModel):
    eligible: int = 0
    ambiguous_credit: int = 0
    not_found: int = 0
    error: int = 0
    skipped_fresh: int = 0

    @property
    def total_processed(self) -> int:
        return self.eligible + self.ambiguous_credit + self.not_found + self.error
