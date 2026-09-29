from uuid import UUID

from src.models.entities import TimestampedEntity


class Question(TimestampedEntity):
    """One aggregate guess prompt owned by a round."""

    id: UUID
    track_ids: list[UUID]
    artist_ids: list[UUID]
