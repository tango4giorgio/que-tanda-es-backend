from uuid import UUID

from src.models.entities import TimestampedEntity


class Artist(TimestampedEntity):
    """A canonical performer/orchestra, reusable across any number of games/questions
    (data-model.md `artist`)."""

    id: UUID
    display_name: str
    external_ids: dict[str, str] | None = None


class Track(TimestampedEntity):
    """A canonical playable recording, reusable across any number of games/questions
    (data-model.md `track`). External source identifiers live on `TrackProvider` instead."""

    id: UUID
    artist_id: UUID


class TrackProvider(TimestampedEntity):
    """A specific playable source for a track. Stores the provider's own identifier for the
    track rather than a static URL, since provider URLs can expire (research.md §7); a playable
    URL is resolved from `(provider, provider_track_id)` at serving time
    (data-model.md `track_provider`)."""

    id: UUID
    track_id: UUID
    provider: str
    provider_track_id: str
    title: str | None = None
    duration_ms: int | None = None
