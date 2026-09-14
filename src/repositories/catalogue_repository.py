from collections.abc import Iterable

from psycopg import Connection

from src.models.track_entry import CatalogueTrackEntry


class CatalogueRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def get_usable_catalogue(self) -> tuple[list[tuple[str, str]], list[CatalogueTrackEntry]]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT o.id, o.display_name, t.id, t.orchestra_id, t.recording_id,
                       t.title, t.preview_url, t.duration_ms, t.is_usable
                FROM catalogue.orchestra AS o
                LEFT JOIN catalogue.track_entry AS t
                  ON t.orchestra_id = o.id AND t.is_usable
                ORDER BY o.id, t.id
                """
            )
            rows = cursor.fetchall()
        orchestras: list[tuple[str, str]] = []
        tracks: list[CatalogueTrackEntry] = []
        seen_orchestras: set[str] = set()
        for row in rows:
            orchestra_id, display_name = row[0], row[1]
            if orchestra_id not in seen_orchestras:
                orchestras.append((orchestra_id, display_name))
                seen_orchestras.add(orchestra_id)
            if row[2] is not None:
                tracks.append(
                    CatalogueTrackEntry(
                        id=row[2],
                        orchestra_id=row[3],
                        recording_id=row[4],
                        title=row[5],
                        preview_url=row[6],
                        duration_ms=row[7],
                        is_usable=row[8],
                    )
                )
        return orchestras, tracks

    def upsert_orchestra(
        self, orchestra_id: str, display_name: str, artist_id: str | None = None
    ) -> None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO catalogue.orchestra (id, display_name, artist_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO UPDATE
                SET display_name = EXCLUDED.display_name,
                    artist_id = COALESCE(EXCLUDED.artist_id, catalogue.orchestra.artist_id)
                """,
                (orchestra_id, display_name, artist_id),
            )

    def upsert_track_entry(self, track: CatalogueTrackEntry) -> None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO catalogue.track_entry
                    (id, orchestra_id, recording_id, title, preview_url, duration_ms)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    orchestra_id = EXCLUDED.orchestra_id,
                    recording_id = EXCLUDED.recording_id,
                    title = EXCLUDED.title,
                    preview_url = EXCLUDED.preview_url,
                    duration_ms = EXCLUDED.duration_ms,
                    updated_at = now()
                """,
                (
                    track.id,
                    track.orchestra_id,
                    track.recording_id,
                    track.title,
                    track.preview_url,
                    track.duration_ms,
                ),
            )

    def get_track_entry_with_canonical_links(self, track_id: str) -> dict[str, str | None] | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT t.id, t.recording_id, r.artist_id
                FROM catalogue.track_entry AS t
                LEFT JOIN music.recording AS r ON r.id = t.recording_id
                WHERE t.id = %s
                """,
                (track_id,),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return {"id": row[0], "recordingId": row[1], "artistId": row[2]}

    def commit(self) -> None:
        self.conn.commit()


def upsert_many(repository: CatalogueRepository, tracks: Iterable[CatalogueTrackEntry]) -> None:
    for track in tracks:
        repository.upsert_track_entry(track)
