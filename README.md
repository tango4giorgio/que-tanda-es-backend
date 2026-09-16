# Tango Music Game Backend

Read-only round delivery for the tango music guessing game. Supabase stores provider links
between canonical MusicBrainz recording IDs and playable URLs, plus a rebuildable derived cache
containing only the artist fields needed to select a round.

## Local setup

```sh
python3.12 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
export DATABASE_URL='postgresql://user:password@host:5432/database'
psql "$DATABASE_URL" -f src/migrations/0001_create_catalogue_schema.sql
psql "$DATABASE_URL" -f src/migrations/0002_create_musicbrainz_recording_cache.sql
psql "$DATABASE_URL" -f src/migrations/0003_create_feedback_schema.sql
pytest -q
ruff check .
```

For local development, `DATABASE_URL` may point to a disposable PostgreSQL database. In Lambda,
set `DATABASE_URL_PARAMETER_NAME`; the service retrieves and caches the Supabase
transaction-pooler URL from an AWS SSM Parameter Store `SecureString` parameter (free Standard
tier, AWS-managed KMS key — no per-secret charge). Optional settings are:

- `DATABASE_CONNECT_TIMEOUT_SECONDS` (default `5`)
- `DATABASE_STATEMENT_TIMEOUT_MS` (default `5000`)
- `LOG_LEVEL` (default `INFO`)

## Releasing Lambda packages

`backend-infra`'s Terraform config does not build Lambda packages locally — it downloads them
from tagged GitHub Releases of this repo. To publish a new deployable version:

```sh
git tag v0.2.0
git push origin v0.2.0
```

Pushing a `v*` tag triggers `.github/workflows/release.yml`, which builds `get_round.zip`,
`gateway.zip`, and `submit_feedback.zip` (vendoring dependencies for the `python3.12`/`arm64`
Lambda runtime, matching `backend-infra`'s `lambda_*.tf`) and publishes them as assets on a
GitHub Release named after the tag. Then set `backend_release_tag = "v0.2.0"` in
`backend-infra/terraform.tfvars` and re-apply.

## Load recording provider links

The loader input must already be enriched with MusicBrainz recording IDs:

```json
{
  "recordings": [
    {
      "musicBrainzRecordingId": "5a5d9d31-64a7-4a5d-87bd-1934d7efbb84",
      "sources": [
        {
          "provider": "archive.org",
          "url": "https://archive.org/download/example/track.mp3",
          "durationMs": 180000
        }
      ]
    }
  ]
}
```

One recording may contain multiple sources from the same or different providers.

```sh
python scripts/load_provider_links.py --source recording-provider-links.json --dry-run
python scripts/load_provider_links.py --source recording-provider-links.json
python scripts/load_provider_links.py --source recording-provider-links.json
```

The dry run validates without writing. Repeating a real load updates the same composite keys
and does not create duplicate rows. Invalid provider sources are skipped and reported to
standard error.

## API

`GET /round` returns one complete round with exactly three artist choices and one to three
playable tracks, plus a `roundToken` string that uniquely identifies the round. Repeated
`excludeArtist` query parameters are accepted. Responses use `Cache-Control: no-store`;
deployed responses require HTTPS preview URLs. The endpoint returns 400 for malformed
exclusions, 422 when no complete round remains, and 503 for dependency failures.

`POST /feedback` records one anonymous guess/skip outcome for stats purposes only — it has no
gameplay effect and stores no player-identifying data. The request body carries the round's
`roundToken`, the track position, recording ID, correct and guessed artist IDs, the outcome
(`correct`/`wrong`/`skipped`), and the elapsed time in milliseconds. Successful submissions
return 202; malformed submissions return 400 (`INVALID_FEEDBACK`); dependency failures return
503 (`FEEDBACK_SERVICE_UNAVAILABLE`). See
`../specs/014-guess-feedback-stats/contracts/submit-feedback.md` for the full contract.

The runtime uses Supabase transaction pooling, disables prepared statements, reuses at most one
validated connection per warm Lambda execution environment, and applies bounded connection and
statement timeouts.

## MusicBrainz boundary

The round endpoint never calls MusicBrainz. Refresh the derived cache with an identifying
application version and maintainer contact:

```sh
python3 scripts/refresh_musicbrainz_cache.py --dry-run
python3 scripts/refresh_musicbrainz_cache.py --status
python3 scripts/refresh_musicbrainz_cache.py --force
```

Refreshes use exact recording MBIDs, serial requests, and a minimum one-second interval.
Fresh rows are skipped unless `--force` is supplied. The command reports eligible,
ambiguous-credit, not-found, failed, and skipped-fresh counts; `--dry-run` does not write.
Configure `MUSICBRAINZ_APPLICATION`, `MUSICBRAINZ_VERSION`, `MUSICBRAINZ_MAINTAINER`,
`MUSICBRAINZ_CACHE_FRESHNESS_SECONDS`, and `MUSICBRAINZ_TIMEOUT_SECONDS` as required.

## Validation

```sh
pytest -q
ruff check .
```

Database-backed integration tests run when `DATABASE_URL` is configured and are otherwise
reported as skipped. The local invocation helper requires a populated database and supports
repeated exclusions:

```sh
python3 -m tests.tools.invoke_get_round
python3 -m tests.tools.invoke_get_round --exclude-artist 11111111-1111-1111-1111-111111111111
```

## Performance measurement

`tests/tools/measure_round_latency.py` seeds a deterministic, disposable dataset and measures
warm `GET /round` invocation latency directly against the Lambda handler:

```sh
python3 -m tests.tools.measure_round_latency \
  --seed-rows 10000 --iterations 200 --warmup 10
```

The helper refuses to seed a database that already contains provider-link rows unless
`--allow-seed-on-existing-data` is passed, and it deletes the rows it inserted once measurement
completes (pass `--keep-seed-data` to retain them). Point `DATABASE_URL` at an empty, disposable
PostgreSQL instance before running it, for example a throwaway Docker container:

```sh
docker run -d --name tango-round-perf -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=tango \
  -p 5433:5432 postgres:16
export DATABASE_URL='postgresql://postgres:postgres@localhost:5433/tango'
python3 -m tests.tools.measure_round_latency --seed-rows 10000 --iterations 200 --warmup 10
docker rm -f tango-round-perf
```

**Measured result (2026-09-15, disposable PostgreSQL 16 in a local container, 10,000 seeded
provider-link and cache rows across 400 artists, 200 warm iterations after 10 warm-up calls):**
`median_ms=55.54`, `p95_ms=98.25`, meeting the warm `GET /round` p95 < 500 ms target (SC-005).
An initial measurement against the unoptimised query (fetching and validating every eligible
provider-link row per request) recorded `p95_ms=1018.82`, which failed the target; the round
repository and service were changed to fetch only the distinct eligible artists and the chosen
correct artist's recordings per request, which resolved the regression. This is a local,
single-process measurement, not a deployed Lambda cold/warm benchmark; treat it as a reproducible
lower bound rather than a production SLA guarantee.

## Gateway overhead measurement

`tests/tools/measure_gateway_overhead.py` measures the processing overhead the reverse-proxy
gateway itself adds on top of a target Lambda invocation, using a stubbed `lambda` client so no
AWS calls or target function execution are involved:

```sh
POWERTOOLS_LOG_LEVEL=WARNING python3 -m tests.tools.measure_gateway_overhead \
  --iterations 1000 --warmup 50
```

**Measured result (2026-09-15, local process, stubbed target invocation, 1000 warm iterations
after 50 warm-up calls):** `median_ms=0.42`, `p95_ms=0.62`, `max_ms=1.47`, comfortably meeting the
gateway-added-overhead p95 < 20 ms target (SC-002). This isolates routing/config-lookup/event
translation/response-parsing cost only; it excludes real network/`boto3.invoke` latency and the
target Lambda's own execution time, both of which are outside the gateway's control.

## Gateway quickstart validation

`specs/013-lambda-reverse-proxy/quickstart.md` scenarios 1-3 (no AWS credentials required) were
executed and passed on 2026-09-15:

1. `pytest tests/unit/test_routing_config.py tests/unit/test_gateway_service.py
   tests/contract/test_gateway_handler.py -v` — all 24 tests passed.
2. `python3 -m tests.tools.invoke_gateway --method GET --path /round` (relays the real
   `get_round` handler in-process), `--method POST --path /round` (`405`), and `--method GET
   --path /unknown` (`404`) all returned the expected results.
3. `terraform fmt -check` and `terraform validate` in `backend-infra/` both succeeded.

Scenario 4 (real-AWS `terraform apply` + `curl` against a deployed gateway endpoint) requires
live AWS credentials and a built `gateway.zip` package and was not executed here, consistent with
the same operational limitation recorded for feature 011 (`specs/011-backend-round-delivery/tasks.md`
T046).

## Infrastructure

Terraform is maintained separately in the sibling `backend-infra/` repository. See
`../backend-infra/README.md` for Supabase and AWS provisioning. Database migrations remain here
because they evolve with the application data model.
