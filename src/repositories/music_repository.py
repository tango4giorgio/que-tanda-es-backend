from psycopg import Connection


class MusicRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def upsert_artist(self, artist_id: str, name: str, mbid_known: bool) -> None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO music.artist (id, name, mbid_known)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    mbid_known = EXCLUDED.mbid_known
                """,
                (artist_id, name, mbid_known),
            )

    def upsert_recording(
        self, recording_id: str, artist_id: str, title: str, mbid_known: bool
    ) -> None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO music.recording (id, artist_id, title, mbid_known)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    artist_id = EXCLUDED.artist_id,
                    title = EXCLUDED.title,
                    mbid_known = EXCLUDED.mbid_known
                """,
                (recording_id, artist_id, title, mbid_known),
            )
