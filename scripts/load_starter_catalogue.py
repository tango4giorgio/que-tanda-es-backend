import argparse
import json
import sys
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path

from src.models.track_entry import CatalogueTrackEntry
from src.repositories.catalogue_repository import CatalogueRepository
from src.repositories.db import connection
from src.repositories.music_repository import MusicRepository


@dataclass
class LoadSummary:
    orchestras: int = 0
    tracks: int = 0
    skipped: int = 0


def load(source: Path, dry_run: bool = False) -> LoadSummary:
    payload = json.loads(source.read_text(encoding="utf-8"))
    summary = LoadSummary()
    with (connection() if not dry_run else nullcontext()) as conn:
        catalogue = CatalogueRepository(conn) if conn is not None else None
        music = MusicRepository(conn) if conn is not None else None
        for orchestra in payload.get("orchestras", []):
            orchestra_id = orchestra.get("id")
            display_name = orchestra.get("displayName")
            if not orchestra_id or not display_name:
                summary.skipped += 1
                print("Skipped orchestra: missing id/displayName", file=sys.stderr)
                continue
            if not dry_run and catalogue is not None:
                catalogue.upsert_orchestra(orchestra_id, display_name)
            summary.orchestras += 1

        for source_track in payload.get("tracks", []):
            try:
                track = CatalogueTrackEntry(
                    id=source_track["id"],
                    orchestra_id=source_track["orchestraId"],
                    title=source_track["title"],
                    preview_url=source_track["previewUrl"],
                    duration_ms=round(source_track["durationMs"]),
                    recording_id=source_track.get("recordingId"),
                )
            except (KeyError, TypeError, ValueError) as error:
                summary.skipped += 1
                print(f"Skipped track: {error}", file=sys.stderr)
                continue
            if not dry_run and catalogue is not None and music is not None:
                if track.recording_id:
                    artist_id = source_track.get("artistId")
                    artist_name = source_track.get("artistName")
                    if artist_id and artist_name:
                        music.upsert_artist(
                            artist_id,
                            artist_name,
                            bool(source_track.get("artistMbidKnown")),
                        )
                        music.upsert_recording(
                            track.recording_id,
                            artist_id,
                            source_track.get("recordingTitle", track.title),
                            bool(source_track.get("recordingMbidKnown")),
                        )
                catalogue.upsert_track_entry(track)
            summary.tracks += 1
        if not dry_run:
            catalogue.commit()
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Load the starter catalogue into Supabase")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    summary = load(args.source, args.dry_run)
    mode = "validated" if args.dry_run else "loaded"
    print(
        f"{mode}: {summary.orchestras} orchestras, {summary.tracks} tracks, "
        f"{summary.skipped} skipped"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
