import argparse
import json
import sys
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path

from src.models.provider_source import ProviderSource
from src.repositories.catalogue_repository import CatalogueRepository
from src.repositories.db import connection


@dataclass
class LoadSummary:
    sources: int = 0
    skipped: int = 0


def load(source_path: Path, dry_run: bool = False) -> LoadSummary:
    try:
        payload = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Unable to read provider-link input: {error}") from error
    recordings = payload.get("recordings") if isinstance(payload, dict) else None
    if not isinstance(recordings, list):
        raise ValueError("Provider-link input must contain a recordings array")

    summary = LoadSummary()
    with connection() if not dry_run else nullcontext() as conn:
        repository = CatalogueRepository(conn) if conn is not None else None
        for recording in recordings:
            if not isinstance(recording, dict):
                summary.skipped += 1
                print("Skipped provider source: recording must be an object", file=sys.stderr)
                continue
            recording_id = recording.get("musicBrainzRecordingId")
            sources = recording.get("sources")
            if not isinstance(sources, list) or not sources:
                summary.skipped += 1
                print(
                    "Skipped provider source: sources must be a non-empty array",
                    file=sys.stderr,
                )
                continue
            for raw_source in sources:
                try:
                    if not isinstance(raw_source, dict):
                        raise TypeError("source must be an object")
                    source = ProviderSource(
                        musicbrainz_recording_id=recording_id,
                        provider=raw_source["provider"],
                        provider_url=raw_source["url"],
                        duration_ms=(
                            round(raw_source["durationMs"])
                            if raw_source.get("durationMs") is not None
                            else None
                        ),
                    )
                except (KeyError, TypeError, ValueError) as error:
                    summary.skipped += 1
                    print(f"Skipped provider source: {error}", file=sys.stderr)
                    continue
                if not dry_run and repository is not None:
                    repository.upsert_source(source)
                summary.sources += 1
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Load MusicBrainz recording-to-provider links into Supabase"
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    summary = load(args.source, args.dry_run)
    mode = "validated" if args.dry_run else "loaded"
    print(f"{mode}: {summary.sources} provider sources, {summary.skipped} skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
