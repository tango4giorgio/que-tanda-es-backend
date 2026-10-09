from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.models.entities import TimestampedEntity


class Session(TimestampedEntity):
    """A tracked gameplay session (data-model.md `session`)."""

    id: UUID
    started_at: datetime
    last_interaction_at: datetime


class SessionCreated(BaseModel):
    """Response body for `POST /session` (data-model.md Session Creation Response)."""

    session_id: UUID = Field(serialization_alias="sessionId")
    started_at: datetime = Field(serialization_alias="startedAt")

    model_config = ConfigDict(populate_by_name=True)
