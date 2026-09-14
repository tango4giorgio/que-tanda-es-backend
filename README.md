# Tango Music Game Backend

Read-only catalogue API for the tango music guessing game. The service runs on AWS Lambda behind API Gateway and reads catalogue data from Supabase Postgres.

## Local setup

```sh
python3.12 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
export DATABASE_URL='postgresql://user:password@host:5432/database'
pytest
```

Apply `src/migrations/0001_create_music_schema.sql` and `src/migrations/0002_create_catalogue_schema.sql` to the target database before loading data.

## Load the starter catalogue

The MVP uses a one-off, idempotent loader rather than a write API:

```sh
python scripts/load_starter_catalogue.py \
  --source ../frontend/public/catalogue/starter-catalogue.json
```

Validate without writing:

```sh
python scripts/load_starter_catalogue.py \
  --source ../frontend/public/catalogue/starter-catalogue.json \
  --dry-run
```

## API

`GET /catalogue` returns the frontend-compatible catalogue response. See the feature contract at `../specs/010-backend-catalogue-api/contracts/get-catalogue.md`.

The service reads `DATABASE_URL` directly for local execution. In AWS, the Lambda environment should resolve the Supabase connection string from the configured Secrets Manager secret before opening a database connection.

The frontend documentation still describes the bundled catalogue at
`frontend/public/catalogue/starter-catalogue.json`; update that runtime-loading documentation
when the frontend is switched to call the deployed `GET /catalogue` endpoint.

## Current validation

- `pytest -q`: 6 passed, 4 Postgres integration tests skipped because no `DATABASE_URL` was configured.
- Starter-catalogue dry run: 5 orchestras, 296 tracks, 0 skipped.
- `ruff check .`: passed.

## Infrastructure

Terraform is maintained separately in the sibling `backend-infra/` folder. See
`../backend-infra/README.md` for Supabase and AWS provisioning. Database migrations remain in
this backend folder because they evolve with the application data model.
