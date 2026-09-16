import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx

from src.config import (
    musicbrainz_base_url,
    musicbrainz_cache_freshness_seconds,
    musicbrainz_timeout_seconds,
    musicbrainz_user_agent,
)
from src.models.musicbrainz_cache import MetadataStatus, MusicBrainzCacheRow, RefreshResult
from src.repositories.catalogue_repository import CatalogueRepository
from src.repositories.db import connection


def _source_updated_at(payload: dict) -> datetime | None:
    value = payload.get("last-updated")
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def derive_cache_row(
    recording_id: UUID, payload: dict, fetched_at: datetime
) -> MusicBrainzCacheRow:
    credits = payload.get("artist-credit") or []
    artists = {
        credit.get("artist", {}).get("id"): credit.get("artist", {}).get("name")
        for credit in credits
        if credit.get("artist", {}).get("id") and credit.get("artist", {}).get("name")
    }
    if len(artists) == 1:
        artist_id, artist_name = next(iter(artists.items()))
        status = MetadataStatus.ELIGIBLE
        answer_artist_id = UUID(artist_id)
    elif not payload:
        status = MetadataStatus.NOT_FOUND
        answer_artist_id = None
        artist_name = None
    else:
        status = MetadataStatus.AMBIGUOUS_CREDIT
        answer_artist_id = None
        artist_name = None
    payload_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return MusicBrainzCacheRow(
        musicbrainz_recording_id=recording_id,
        answer_artist_id=answer_artist_id,
        answer_artist_name=artist_name,
        metadata_status=status,
        source_updated_at=_source_updated_at(payload),
        fetched_at=fetched_at,
        payload_hash=payload_hash,
    )


def fetch_recording(client: httpx.Client, recording_id: str) -> tuple[dict, MetadataStatus | None]:
    response = client.get(
        f"/ws/2/recording/{recording_id}",
        params={"inc": "artist-credits", "fmt": "json"},
    )
    if response.status_code == 404:
        return {}, MetadataStatus.NOT_FOUND
    response.raise_for_status()
    return response.json(), None


def refresh(*, dry_run: bool = False, force: bool = False) -> RefreshResult:
    now = datetime.now(UTC)
    result = RefreshResult()
    headers = {"User-Agent": musicbrainz_user_agent(), "Accept": "application/json"}
    with connection() as conn:
        repository = CatalogueRepository(conn)
        recording_ids = repository.get_recording_ids()
        with httpx.Client(
            base_url=musicbrainz_base_url().rstrip("/"),
            headers=headers,
            timeout=musicbrainz_timeout_seconds(),
        ) as client:
            for index, recording_id in enumerate(recording_ids):
                existing = repository.get_cache_row(recording_id)
                if (
                    existing
                    and not force
                    and existing.fetched_at >= now - timedelta(
                        seconds=musicbrainz_cache_freshness_seconds()
                    )
                ):
                    result.skipped_fresh += 1
                    continue
                if index:
                    import time

                    time.sleep(1)
                fetched_at = datetime.now(UTC)
                try:
                    payload, special_status = fetch_recording(client, recording_id)
                    row = derive_cache_row(UUID(recording_id), payload, fetched_at)
                    if special_status is not None:
                        row = row.model_copy(update={"metadata_status": special_status})
                except (httpx.HTTPError, ValueError, TypeError) as error:
                    result.error += 1
                    error_row = MusicBrainzCacheRow(
                        musicbrainz_recording_id=UUID(recording_id),
                        metadata_status=MetadataStatus.ERROR,
                        fetched_at=fetched_at,
                        payload_hash=hashlib.sha256(str(error).encode()).hexdigest(),
                    )
                    if not dry_run:
                        repository.upsert_cache_row(error_row)
                    continue
                status_name = row.metadata_status.value
                setattr(result, status_name, getattr(result, status_name) + 1)
                if not dry_run:
                    repository.upsert_cache_row(row)
    return result


def status() -> dict[str, int]:
    with connection() as conn:
        return CatalogueRepository(conn).get_cache_status_counts(
            musicbrainz_cache_freshness_seconds()
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh the derived MusicBrainz recording cache")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    try:
        result = status() if args.status else refresh(dry_run=args.dry_run, force=args.force)
    except Exception as error:
        print(f"refresh failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            result if isinstance(result, dict) else result.model_dump(),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
