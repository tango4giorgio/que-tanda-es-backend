from psycopg import Connection

from src.models.musicbrainz_cache import MusicBrainzCacheRow
from src.models.provider_source import ProviderSource


class CatalogueRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def get_usable_sources(self) -> list[ProviderSource]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT musicbrainz_recording_id, provider, provider_url, duration_ms, is_usable
                FROM catalogue.recording_provider
                WHERE is_usable
                ORDER BY musicbrainz_recording_id, provider, provider_url
                """
            )
            rows = cursor.fetchall()
        return [
            ProviderSource(
                musicbrainz_recording_id=row[0],
                provider=row[1],
                provider_url=row[2],
                duration_ms=row[3],
                is_usable=row[4],
            )
            for row in rows
        ]

    def upsert_source(self, source: ProviderSource) -> None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO catalogue.recording_provider
                    (musicbrainz_recording_id, provider, provider_url, duration_ms)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (musicbrainz_recording_id, provider, provider_url) DO UPDATE SET
                    duration_ms = EXCLUDED.duration_ms,
                    updated_at = now()
                """,
                (
                    source.musicbrainz_recording_id,
                    source.provider,
                    str(source.provider_url),
                    source.duration_ms,
                ),
            )

    def get_sources_for_recording(self, recording_id: str) -> list[ProviderSource]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT musicbrainz_recording_id, provider, provider_url, duration_ms, is_usable
                FROM catalogue.recording_provider
                WHERE musicbrainz_recording_id = %s AND is_usable
                ORDER BY provider, provider_url
                """,
                (recording_id,),
            )
            rows = cursor.fetchall()
        return [
            ProviderSource(
                musicbrainz_recording_id=row[0],
                provider=row[1],
                provider_url=row[2],
                duration_ms=row[3],
                is_usable=row[4],
            )
            for row in rows
        ]

    def commit(self) -> None:
        self.conn.commit()

    def get_recording_ids(self) -> list[str]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT musicbrainz_recording_id
                FROM catalogue.recording_provider
                ORDER BY musicbrainz_recording_id
                """
            )
            return [str(row[0]) for row in cursor.fetchall()]

    def get_cache_row(self, recording_id: str) -> MusicBrainzCacheRow | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT musicbrainz_recording_id, answer_artist_id, answer_artist_name,
                       metadata_status, source_updated_at, fetched_at, payload_hash
                FROM catalogue.musicbrainz_recording_cache
                WHERE musicbrainz_recording_id = %s
                """,
                (recording_id,),
            )
            row = cursor.fetchone()
        return (
            MusicBrainzCacheRow(
                musicbrainz_recording_id=row[0],
                answer_artist_id=row[1],
                answer_artist_name=row[2],
                metadata_status=row[3],
                source_updated_at=row[4],
                fetched_at=row[5],
                payload_hash=row[6],
            )
            if row
            else None
        )

    def upsert_cache_row(self, row: MusicBrainzCacheRow) -> None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO catalogue.musicbrainz_recording_cache
                    (musicbrainz_recording_id, answer_artist_id, answer_artist_name,
                     metadata_status, source_updated_at, fetched_at, payload_hash)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (musicbrainz_recording_id) DO UPDATE SET
                    answer_artist_id = EXCLUDED.answer_artist_id,
                    answer_artist_name = EXCLUDED.answer_artist_name,
                    metadata_status = EXCLUDED.metadata_status,
                    source_updated_at = EXCLUDED.source_updated_at,
                    fetched_at = EXCLUDED.fetched_at,
                    payload_hash = EXCLUDED.payload_hash
                """,
                (
                    row.musicbrainz_recording_id,
                    row.answer_artist_id,
                    row.answer_artist_name,
                    row.metadata_status,
                    row.source_updated_at,
                    row.fetched_at,
                    row.payload_hash,
                ),
            )

    def get_cache_status_counts(self, freshness_seconds: int = 86_400) -> dict[str, int]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT metadata_status, count(*),
                       count(*) FILTER (
                           WHERE fetched_at >= now() - (%s * interval '1 second')
                       )
                FROM catalogue.musicbrainz_recording_cache
                GROUP BY metadata_status
                ORDER BY metadata_status
                """
                ,
                (freshness_seconds,),
            )
            counts = {row[0]: row[1] for row in cursor.fetchall()}
            cursor.execute(
                """
                SELECT
                    count(*) FILTER (
                        WHERE fetched_at >= now() - (%s * interval '1 second')
                    ),
                    count(*) FILTER (
                        WHERE fetched_at < now() - (%s * interval '1 second')
                    )
                FROM catalogue.musicbrainz_recording_cache
                """,
                (freshness_seconds, freshness_seconds),
            )
            fresh, stale = cursor.fetchone()
            counts["fresh"] = fresh
            counts["stale"] = stale
            return counts
