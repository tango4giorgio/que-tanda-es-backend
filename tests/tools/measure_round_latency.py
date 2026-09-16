"""Reproducible local measurement of warm GET /round latency.

This helper seeds a deterministic, disposable dataset of provider links and
derived MusicBrainz cache rows, measures warm invocation latency of the round
Lambda handler directly, and reports p50/p95 results. It is designed to run
against an isolated PostgreSQL database (for example, a throwaway Docker
container) and refuses to seed on top of pre-existing rows unless explicitly
overridden, to avoid damaging real data.
"""

import argparse
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid5

import psycopg

from src.config import database_url
from src.handlers.get_round import lambda_handler

SEED_NAMESPACE = UUID("6b6f6f6c-6161-6161-6161-616161616161")
MIGRATIONS = [
    Path(__file__).parents[2] / "src" / "migrations" / "0001_create_catalogue_schema.sql",
    Path(__file__).parents[2]
    / "src"
    / "migrations"
    / "0002_create_musicbrainz_recording_cache.sql",
]


def _deterministic_uuid(label: str) -> UUID:
    return uuid5(SEED_NAMESPACE, label)


def apply_migrations(conn: psycopg.Connection) -> None:
    for migration in MIGRATIONS:
        conn.execute(migration.read_text(encoding="utf-8"))
    conn.commit()


def existing_row_count(conn: psycopg.Connection) -> int:
    with conn.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM catalogue.recording_provider")
        return cursor.fetchone()[0]


def seed_dataset(
    conn: psycopg.Connection, *, row_count: int, artist_count: int
) -> list[UUID]:
    """Insert a deterministic set of recordings, provider links, and eligible
    cache rows spread across `artist_count` distinct artists. Returns the
    recording IDs inserted so the caller can clean them up afterwards."""
    recording_ids: list[UUID] = []
    with conn.cursor() as cursor:
        with cursor.copy(
            "COPY catalogue.recording_provider "
            "(musicbrainz_recording_id, provider, provider_url, duration_ms) "
            "FROM STDIN"
        ) as copy:
            for index in range(row_count):
                recording_id = _deterministic_uuid(f"recording-{index}")
                recording_ids.append(recording_id)
                copy.write_row(
                    (
                        str(recording_id),
                        "perf-fixture",
                        f"https://example.test/perf/{recording_id}.mp3",
                        120_000,
                    )
                )
        fetched_at = datetime.now(UTC).isoformat()
        with cursor.copy(
            "COPY catalogue.musicbrainz_recording_cache "
            "(musicbrainz_recording_id, answer_artist_id, answer_artist_name, "
            "metadata_status, fetched_at, payload_hash) "
            "FROM STDIN"
        ) as copy:
            for index, recording_id in enumerate(recording_ids):
                artist_index = index % artist_count
                artist_id = _deterministic_uuid(f"artist-{artist_index}")
                copy.write_row(
                    (
                        str(recording_id),
                        str(artist_id),
                        f"Perf Fixture Orchestra {artist_index}",
                        "eligible",
                        fetched_at,
                        f"perf-seed-{index}",
                    )
                )
    conn.commit()
    return recording_ids


def cleanup_dataset(conn: psycopg.Connection, recording_ids: list[UUID]) -> None:
    ids = [str(recording_id) for recording_id in recording_ids]
    with conn.cursor() as cursor:
        cursor.execute(
            "DELETE FROM catalogue.musicbrainz_recording_cache "
            "WHERE musicbrainz_recording_id = ANY(%s::uuid[])",
            (ids,),
        )
        cursor.execute(
            "DELETE FROM catalogue.recording_provider "
            "WHERE musicbrainz_recording_id = ANY(%s::uuid[])",
            (ids,),
        )
    conn.commit()


def measure(*, iterations: int, warmup: int) -> list[float]:
    event = {
        "version": "2.0",
        "routeKey": "GET /round",
        "rawPath": "/round",
        "requestContext": {
            "stage": "$default",
            "http": {"method": "GET", "path": "/round"},
        },
    }
    for _ in range(warmup):
        result = lambda_handler(event, None)
        if result["statusCode"] != 200:
            raise SystemExit(f"warm-up round invocation failed: {result['statusCode']}")
    samples = []
    for _ in range(iterations):
        started = time.perf_counter()
        result = lambda_handler(event, None)
        samples.append((time.perf_counter() - started) * 1_000)
        if result["statusCode"] != 200:
            raise SystemExit(f"round invocation failed: {result['statusCode']}")
    return samples


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure local warm round invocation latency against a seeded dataset"
    )
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument(
        "--seed-rows",
        type=int,
        default=0,
        help="Insert this many deterministic provider-link and cache rows before measuring",
    )
    parser.add_argument(
        "--seed-artists",
        type=int,
        default=0,
        help="Distinct artists to spread seeded rows across (default: rows // 25, min 3)",
    )
    parser.add_argument(
        "--keep-seed-data",
        action="store_true",
        help="Do not delete the seeded rows after measuring",
    )
    parser.add_argument(
        "--allow-seed-on-existing-data",
        action="store_true",
        help="Permit seeding even when catalogue.recording_provider already has rows",
    )
    args = parser.parse_args()

    recording_ids: list[UUID] = []
    if args.seed_rows > 0:
        artist_count = args.seed_artists or max(3, args.seed_rows // 25)
        with psycopg.connect(database_url(), prepare_threshold=None) as seed_conn:
            apply_migrations(seed_conn)
            existing = existing_row_count(seed_conn)
            if existing > 0 and not args.allow_seed_on_existing_data:
                raise SystemExit(
                    f"refusing to seed: catalogue.recording_provider already has {existing} "
                    "row(s). Point DATABASE_URL at an empty, disposable database, or pass "
                    "--allow-seed-on-existing-data to proceed anyway."
                )
            recording_ids = seed_dataset(
                seed_conn, row_count=args.seed_rows, artist_count=artist_count
            )
            print(
                f"seeded rows={len(recording_ids)} artists={artist_count} "
                f"(database previously had {existing} row(s))"
            )

    try:
        samples = measure(iterations=args.iterations, warmup=args.warmup)
    finally:
        if recording_ids and not args.keep_seed_data:
            with psycopg.connect(database_url(), prepare_threshold=None) as cleanup_conn:
                cleanup_dataset(cleanup_conn, recording_ids)
            print(f"cleaned up {len(recording_ids)} seeded row(s)")

    samples.sort()
    p50 = statistics.median(samples)
    p95 = samples[min(len(samples) - 1, int(len(samples) * 0.95))]
    target_met = p95 < 500
    print(
        f"iterations={len(samples)} median_ms={p50:.2f} p95_ms={p95:.2f} "
        f"target_below_500ms={'yes' if target_met else 'no'}"
    )
    return 0 if target_met else 1


if __name__ == "__main__":
    raise SystemExit(main())
