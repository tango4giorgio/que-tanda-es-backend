from dataclasses import dataclass
from uuid import UUID

from psycopg import Connection

from src.models.provider_source import ProviderSource


@dataclass(frozen=True)
class EligibleArtist:
    artist_id: UUID
    artist_name: str


@dataclass(frozen=True)
class PlayableRecording:
    recording_id: UUID
    artist_id: UUID
    artist_name: str
    source: ProviderSource


class RoundRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def get_eligible_artists(
        self, excluded_artist_ids: frozenset[UUID] = frozenset()
    ) -> list[EligibleArtist]:
        """Return the distinct non-excluded artists with at least one usable
        recording. This avoids materialising every provider-link row so it
        stays fast regardless of catalogue size."""
        excluded = list(excluded_artist_ids)
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT c.answer_artist_id, c.answer_artist_name
                FROM catalogue.musicbrainz_recording_cache AS c
                JOIN catalogue.recording_provider AS p
                  ON p.musicbrainz_recording_id = c.musicbrainz_recording_id
                WHERE c.metadata_status = 'eligible'
                  AND p.is_usable
                  AND NOT (c.answer_artist_id = ANY(%s::uuid[]))
                """,
                (excluded,),
            )
            rows = cursor.fetchall()
        return [EligibleArtist(artist_id=row[0], artist_name=row[1]) for row in rows]

    def get_playable_recordings_for_artist(self, artist_id: UUID) -> list[PlayableRecording]:
        """Return usable recordings for exactly one artist. Selection first
        narrows to one candidate correct artist so this query, unlike a full
        catalogue scan, stays small regardless of total provider-link count."""
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT p.musicbrainz_recording_id, c.answer_artist_id, c.answer_artist_name,
                       p.provider, p.provider_url, p.duration_ms, p.is_usable
                FROM catalogue.recording_provider AS p
                JOIN catalogue.musicbrainz_recording_cache AS c
                  ON c.musicbrainz_recording_id = p.musicbrainz_recording_id
                WHERE p.is_usable
                  AND c.metadata_status = 'eligible'
                  AND c.answer_artist_id = %s
                ORDER BY p.musicbrainz_recording_id, p.provider, p.provider_url
                """,
                (str(artist_id),),
            )
            rows = cursor.fetchall()
        return [
            PlayableRecording(
                recording_id=row[0],
                artist_id=row[1],
                artist_name=row[2],
                source=ProviderSource(
                    musicbrainz_recording_id=row[0],
                    provider=row[3],
                    provider_url=row[4],
                    duration_ms=row[5],
                    is_usable=row[6],
                ),
            )
            for row in rows
        ]
