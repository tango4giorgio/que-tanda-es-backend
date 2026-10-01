"""Reproducible local measurement of warm GET /game latency.

This helper seeds a deterministic, disposable dataset of artist/track/track_provider rows,
measures warm invocation latency of the round Lambda handler directly, and reports p50/p95
results. It is designed to run against an isolated PostgreSQL database (for example, a
throwaway Docker container) and refuses to seed on top of pre-existing rows unless explicitly
overridden, to avoid damaging real data.
"""

import argparse
import statistics
import time
from pathlib import Path
from uuid import UUID, uuid5

import psycopg

from src.config import database_url
from src.handlers.get_game import lambda_handler

SEED_NAMESPACE = UUID("6b6f6f6c-6161-6161-6161-616161616161")
MIGRATIONS = [
    Path(__file__).parents[2] / "src" / "migrations" / "0001_create_schema.sql",
]


def _deterministic_uuid(label: str) -> UUID:
    return uuid5(SEED_NAMESPACE, label)


def apply_migrations(conn: psycopg.Connection) -> None:
    for migration in MIGRATIONS:
        conn.execute(migration.read_text(encoding="utf-8"))
    conn.commit()


def existing_row_count(conn: psycopg.Connection) -> int:
    with conn.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM track_provider")
        return cursor.fetchone()[0]


def seed_dataset(conn: psycopg.Connection, *, row_count: int, artist_count: int) -> list[UUID]:
    """Insert a deterministic set of artists, tracks, and track_provider rows spread across
    `artist_count` distinct artists. Returns the artist IDs inserted so the caller can clean
    them up afterwards."""
    artist_ids: list[UUID] = []
    with conn.cursor() as cursor:
        with cursor.copy("COPY artist (id, display_name) FROM STDIN") as copy:
            for artist_index in range(artist_count):
                artist_id = _deterministic_uuid(f"artist-{artist_index}")
                artist_ids.append(artist_id)
                copy.write_row((str(artist_id), f"Perf Fixture Orchestra {artist_index}"))
        track_ids: list[UUID] = []
        with cursor.copy("COPY track (id, artist_id) FROM STDIN") as copy:
            for index in range(row_count):
                track_id = _deterministic_uuid(f"track-{index}")
                artist_id = artist_ids[index % artist_count]
                track_ids.append(track_id)
                copy.write_row((str(track_id), str(artist_id)))
        with cursor.copy(
            "COPY track_provider (track_id, provider, provider_track_id, duration_ms) "
            "FROM STDIN"
        ) as copy:
            for index, track_id in enumerate(track_ids):
                copy.write_row((str(track_id), "deezer", f"perf-seed-{index}", 120_000))
    conn.commit()
    return artist_ids


def cleanup_dataset(conn: psycopg.Connection, artist_ids: list[UUID]) -> None:
    ids = [str(artist_id) for artist_id in artist_ids]
    with conn.cursor() as cursor:
        cursor.execute("TRUNCATE guess_feedback, round, question, game CASCADE")
        cursor.execute(
            "DELETE FROM track_provider WHERE track_id IN (SELECT id FROM track "
            "WHERE artist_id = ANY(%s::uuid[]))",
            (ids,),
        )
        cursor.execute("DELETE FROM track WHERE artist_id = ANY(%s::uuid[])", (ids,))
        cursor.execute("DELETE FROM artist WHERE id = ANY(%s::uuid[])", (ids,))
    conn.commit()


def measure(*, iterations: int, warmup: int) -> list[float]:
    event = {
        "version": "2.0",
        "routeKey": "GET /game",
        "rawPath": "/game",
        "rawQueryString": "",
        "requestContext": {
            "stage": "$default",
            "http": {"method": "GET", "path": "/game"},
        },
    }
    for _ in range(warmup):
        result = lambda_handler(event, None)
        if result["statusCode"] != 200:
            raise SystemExit(f"warm-up game invocation failed: {result['statusCode']}")
    samples = []
    for _ in range(iterations):
        started = time.perf_counter()
        result = lambda_handler(event, None)
        samples.append((time.perf_counter() - started) * 1_000)
        if result["statusCode"] != 200:
            raise SystemExit(f"game invocation failed: {result['statusCode']}")
    return samples


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure local warm game invocation latency against a seeded dataset"
    )
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument(
        "--seed-rows",
        type=int,
        default=0,
        help="Insert this many deterministic track/track_provider rows before measuring",
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
        help="Permit seeding even when track_provider already has rows",
    )
    args = parser.parse_args()

    artist_ids: list[UUID] = []
    if args.seed_rows > 0:
        artist_count = args.seed_artists or max(3, args.seed_rows // 25)
        with psycopg.connect(database_url(), prepare_threshold=None) as seed_conn:
            apply_migrations(seed_conn)
            existing = existing_row_count(seed_conn)
            if existing > 0 and not args.allow_seed_on_existing_data:
                raise SystemExit(
                    f"refusing to seed: track_provider already has {existing} row(s). Point "
                    "DATABASE_URL at an empty, disposable database, or pass "
                    "--allow-seed-on-existing-data to proceed anyway."
                )
            artist_ids = seed_dataset(
                seed_conn, row_count=args.seed_rows, artist_count=artist_count
            )
            print(
                f"seeded rows={args.seed_rows} artists={artist_count} "
                f"(database previously had {existing} row(s))"
            )

    try:
        samples = measure(iterations=args.iterations, warmup=args.warmup)
    finally:
        if artist_ids and not args.keep_seed_data:
            with psycopg.connect(database_url(), prepare_threshold=None) as cleanup_conn:
                cleanup_dataset(cleanup_conn, artist_ids)
            print(f"cleaned up {len(artist_ids)} seeded artist(s)")

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
