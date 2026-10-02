#!/usr/bin/env bash
set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL must contain the migration_runner connection string}"

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
migrations_dir="${MIGRATIONS_DIR:-$repo_root/src/migrations}"

psql "$DATABASE_URL" \
  --no-psqlrc \
  --set ON_ERROR_STOP=1 <<'SQL'
CREATE TABLE IF NOT EXISTS public.schema_migration (
    filename text PRIMARY KEY,
    checksum text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
);
REVOKE ALL ON public.schema_migration FROM app_runtime;
SQL

shopt -s nullglob
migrations=("$migrations_dir"/*.sql)

if ((${#migrations[@]} == 0)); then
  echo "No migration files found in $migrations_dir" >&2
  exit 1
fi

for migration in "${migrations[@]}"; do
  filename="$(basename "$migration")"
  checksum="$(sha256sum "$migration" | cut -d' ' -f1)"

  applied_checksum="$(
    psql "$DATABASE_URL" \
      --no-psqlrc \
      --tuples-only \
      --no-align \
      --set ON_ERROR_STOP=1 \
      -v migration_filename="$filename" <<'SQL'
SELECT checksum
FROM public.schema_migration
WHERE filename = :'migration_filename';
SQL
  )"
  applied_checksum="${applied_checksum//$'\n'/}"

  if [[ -n "$applied_checksum" ]]; then
    if [[ "$applied_checksum" != "$checksum" ]]; then
      echo "Migration $filename has changed since it was applied." >&2
      echo "Recorded checksum: $applied_checksum" >&2
      echo "Current checksum:  $checksum" >&2
      exit 1
    fi
    echo "Already applied: $filename"
    continue
  fi

  echo "Applying: $filename"
  psql "$DATABASE_URL" \
    --no-psqlrc \
    --set ON_ERROR_STOP=1 \
    --single-transaction \
    -v migration_filename="$filename" \
    -v migration_checksum="$checksum" \
    -f "$migration" \
    -f - <<'SQL'
INSERT INTO public.schema_migration (filename, checksum)
VALUES (:'migration_filename', :'migration_checksum');
SQL
done
