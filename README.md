# Tango Music Game Backend

Round delivery and guess feedback for the tango music guessing game. Every played game, round,
question, track, artist, and guess outcome is persisted as its own relational record (see
`specs/018-game-data-redesign/data-model.md`) so a game's full history can be reconstructed
from the database alone.

## Local setup

```sh
# Start the shared Postgres instance (once; see ../ingestion/README.md for details)
docker compose -f ../ingestion/infra/docker-compose.yml up -d postgres

python3.12 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
export DATABASE_URL='******host.docker.internal:5432/tango_game'
scripts/run_migrations.sh
pytest -q
ruff check .
```

`scripts/run_migrations.sh` applies each versioned SQL file once and records its SHA-256
checksum in `public.schema_migration`. Changing an already-applied migration is rejected;
create a new migration file instead.

`0002_seed_catalogue.sql` contains generated artist and Deezer track seed data. Its artist section
is generated from confirmed ingestion matching; its Deezer track section comes from
`../ingestion/queries/generate_track_seed.sql`. It creates canonical tracks using the existing
internal `artist.id`, seeds only Deezer provider rows, and caches each provider's track title and
duration for display without another provider request.

`0001_create_schema.sql` also adds two catalogue-backed question helpers:

- `create_question_for_artist(number_of_tracks, number_of_choices, artist_id)` inserts and
  returns an aggregate question. It randomly selects one to three provider-backed tracks from
  the supplied artist and mixes that artist with the requested number of distinct, eligible
  artist choices.
- `create_random_question()` selects a random artist with at least three provider-backed
  tracks and calls `create_question_for_artist(3, 3, artist_id)`.

The same schema file creates `admin_question`, with one row per aggregate
question. Its `tracks` and `artists` columns are ordered JSON arrays containing IDs and cached
display titles/names. `correct_artist_id` and `correct_artist_name` are resolved from the
question's tracks. Track titles prefer Deezer and fall back to another cached provider title.

It defines ordered `game_round` and `round_question` association tables instead of direct
ownership columns on `round`. Both use UUID primary keys,
audit timestamps, and unique parent/child and parent/position constraints. Existing gameplay
relationships are represented through these tables from initialisation.

Local development and integration tests reuse the same Postgres instance as the `ingestion`
pipeline (a sibling `tango_game`/`tango_game_test` database on that instance) rather than
provisioning a separate database (see `specs/018-game-data-redesign/research.md` section 1).
For integration tests, point `DATABASE_URL` at the `tango_game_test` database on the same
instance instead; `tests/integration/conftest.py` applies all migrations automatically at
the start of the test session. In Lambda, set `DATABASE_URL_PARAMETER_NAME`; the service
retrieves and caches the Supabase transaction-pooler URL from an AWS SSM Parameter Store
`SecureString` parameter (free Standard tier, AWS-managed KMS key, no per-secret charge).
Optional settings are:

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

Pushing a `v*` tag triggers `.github/workflows/release.yml`, which builds `get_game.zip`,
`get_previews.zip`, `gateway.zip`, `submit_feedback.zip`, and `create_session.zip` for the
`python3.12`/`arm64` Lambda runtime and publishes them as immutable GitHub Release assets.

This repository does not initialise or migrate production databases. The infrastructure
repository checks out the selected backend release, applies its outstanding migrations, and
then deploys its Lambda packages through Terraform. This keeps production orchestration and
all production secrets in one repository.

## API

`GET /game` creates and persists a complete game containing exactly three rounds. Each round
contains three artist choices and one aggregate question. The question exposes its persisted
`questionId` and an ordered list of one to three internal `trackIds`; preview URLs, provider
identifiers, and track titles are deliberately excluded. Repeated `excludeArtist` query
parameters are accepted. The endpoint
returns 400 for malformed exclusions, 422 when a complete game cannot be formed, and 503 for
dependency failures.

`POST /previews` accepts `{"trackIds": ["<track-id>", ...]}` for between 1 and 50 internal
track IDs and returns one playable provider preview per track in request order. Duplicate IDs
are collapsed. The whole request returns 404 if any requested track has no supported preview,
rather than returning a partially successful response.

Preview providers are isolated behind provider adaptors. The Deezer adaptor looks up
`https://api.deezer.com/track/{providerTrackId}` at request time and returns the API's HTTPS
`preview` value, which points to the playable MP3 preview rather than the Deezer track page.
An absent track or preview is treated as unavailable; a Deezer transport or malformed-response
failure returns 503 (`PREVIEW_SERVICE_UNAVAILABLE`).

`POST /feedback` records one anonymous guess/skip outcome for stats purposes only. The request
body carries the `questionId`, one-based `trackPosition`, guessed artist ID (`null` only when
skipped), and outcome
(`correct`/`incorrect`/`skipped`), and the elapsed time in milliseconds. Successful submissions
return 202; malformed submissions, or a second submission for the same `questionId`, return 400
(`INVALID_FEEDBACK`); dependency failures return
503 (`FEEDBACK_SERVICE_UNAVAILABLE`). See
`../specs/018-game-data-redesign/contracts/get-round.md` and
`../specs/018-game-data-redesign/contracts/submit-feedback.md` for the full contracts.

The runtime uses Supabase transaction pooling, disables prepared statements, reuses at most one
validated connection per warm Lambda execution environment, and applies bounded connection and
statement timeouts.

## Validation

```sh
pytest -q
ruff check .
```

Database-backed integration tests run when `DATABASE_URL` is configured and are otherwise
reported as skipped. The local invocation helper requires a populated database and supports
repeated exclusions:

```sh
python3 -m tests.tools.invoke_get_game
python3 -m tests.tools.invoke_get_game --exclude-artist 11111111-1111-1111-1111-111111111111
python3 -m tests.tools.invoke_get_previews aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa
```

## Performance measurement

`tests/tools/measure_game_latency.py` seeds a deterministic, disposable dataset and measures
warm `GET /game` invocation latency directly against the Lambda handler:

```sh
python3 -m tests.tools.measure_game_latency \
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
python3 -m tests.tools.measure_game_latency --seed-rows 10000 --iterations 200 --warmup 10
docker rm -f tango-round-perf
```

The prior `GET /round` measurements are no longer representative because one `GET /game`
request now creates all three rounds. Re-run this helper on a disposable database before
recording a replacement performance baseline.

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
2. `python3 -m tests.tools.invoke_gateway --method GET --path /game` (relays the real
   `get_game` handler in-process), `--method POST --path /game` (`405`), and `--method GET
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
