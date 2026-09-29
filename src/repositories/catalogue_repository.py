from dataclasses import dataclass, field
from uuid import UUID

from psycopg import Connection

from src.models.track import Artist, Track, TrackProvider


@dataclass(frozen=True)
class TrackWithProviders:
    track: Track
    providers: list[TrackProvider] = field(default_factory=list)


class CatalogueRepository:
    """Read-only queries over the canonical artist/track/track_provider catalogue. No
    eligibility/usability flag is applied here — that concept is explicitly out of scope for
    this redesign; any track/provider row present is a candidate (data-model.md `artist`,
    `track`, `track_provider`). Folds in the round-selection responsibilities previously in the
    now-deleted `round_repository.py`."""

    def __init__(self, conn: Connection):
        self.conn = conn

    def get_eligible_artists(
        self, excluded_artist_ids: frozenset[UUID] = frozenset()
    ) -> list[Artist]:
        """Return the distinct non-excluded artists that have at least one track with at
        least one track_provider."""
        excluded = list(excluded_artist_ids)
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT a.id, a.display_name, a.external_ids, a.created_at, a.updated_at
                FROM artist AS a
                JOIN track AS t ON t.artist_id = a.id
                JOIN track_provider AS tp ON tp.track_id = t.id
                WHERE NOT (a.id = ANY(%s::uuid[]))
                ORDER BY a.id
                """,
                (excluded,),
            )
            rows = cursor.fetchall()
        return [
            Artist(
                id=row[0],
                display_name=row[1],
                external_ids=row[2],
                created_at=row[3],
                updated_at=row[4],
            )
            for row in rows
        ]

    def get_tracks_for_artist(self, artist_id: UUID) -> list[TrackWithProviders]:
        """Return this artist's tracks, each with its track_provider rows, so round-selection
        can pick a playable provider without a second round trip per track. Selection first
        narrows to one candidate correct artist so this query stays small regardless of total
        catalogue size."""
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT t.id, t.artist_id, t.created_at, t.updated_at,
                       tp.id, tp.track_id, tp.provider, tp.provider_track_id, tp.title,
                       tp.duration_ms, tp.created_at, tp.updated_at
                FROM track AS t
                JOIN track_provider AS tp ON tp.track_id = t.id
                WHERE t.artist_id = %s
                ORDER BY t.id, tp.id
                """,
                (str(artist_id),),
            )
            rows = cursor.fetchall()
        tracks_by_id: dict[UUID, TrackWithProviders] = {}
        for row in rows:
            track_id = row[0]
            if track_id not in tracks_by_id:
                tracks_by_id[track_id] = TrackWithProviders(
                    track=Track(
                        id=row[0],
                        artist_id=row[1],
                        created_at=row[2],
                        updated_at=row[3],
                    )
                )
            tracks_by_id[track_id].providers.append(
                TrackProvider(
                    id=row[4],
                    track_id=row[5],
                    provider=row[6],
                    provider_track_id=row[7],
                    title=row[8],
                    duration_ms=row[9],
                    created_at=row[10],
                    updated_at=row[11],
                )
            )
        return list(tracks_by_id.values())

    def get_providers_for_tracks(
        self, track_ids: list[UUID]
    ) -> dict[UUID, list[TrackProvider]]:
        if not track_ids:
            return {}
        with self.conn.cursor() as cursor:
            serialised_track_ids = [str(track_id) for track_id in track_ids]
            cursor.execute(
                """
                SELECT tp.id, tp.track_id, tp.provider, tp.provider_track_id, tp.title,
                       tp.duration_ms, tp.created_at, tp.updated_at
                FROM track_provider AS tp
                WHERE tp.track_id = ANY(%s::uuid[])
                ORDER BY array_position(%s::uuid[], tp.track_id), tp.id
                """,
                (serialised_track_ids, serialised_track_ids),
            )
            rows = cursor.fetchall()
        providers: dict[UUID, list[TrackProvider]] = {track_id: [] for track_id in track_ids}
        for row in rows:
            providers[row[1]].append(
                TrackProvider(
                    id=row[0],
                    track_id=row[1],
                    provider=row[2],
                    provider_track_id=row[3],
                    title=row[4],
                    duration_ms=row[5],
                    created_at=row[6],
                    updated_at=row[7],
                )
            )
        return providers
