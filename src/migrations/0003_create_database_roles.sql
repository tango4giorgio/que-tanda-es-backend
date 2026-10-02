-- Splits database access into two roles so the powerful one-off project-creation credential
-- (the Supabase project's initial superuser, used only by Terraform to stand the project up)
-- is never reused for recurring work:
--
--   * migration_runner — owns the schema and every object in it; the only role used to apply
--     migrations (this file and every future one) as part of a release deployment.
--   * app_runtime      — least privilege (read/write data, execute functions, no DDL); the
--     only credential given to the deployed Lambdas (stored in SSM).
--
-- Run once via the project's superuser as part of initial, one-off database setup (only the
-- superuser has the standing privilege to create roles and reassign ownership). Every
-- subsequent migration run, including re-runs of this file as part of a normal release,
-- connects as migration_runner instead — the bootstrap steps below detect that and no-op.
-- Passwords are supplied as psql variables so they are never written into this file:
--   psql "$SUPERUSER_DATABASE_URL" \
--     -v migration_runner_password="$MIGRATION_RUNNER_PASSWORD" \
--     -v app_runtime_password="$APP_RUNTIME_PASSWORD" \
--     -f 0003_create_database_roles.sql

-- psql only substitutes :'variable' tokens outside of quoted strings, so the passwords are
-- threaded through a session GUC rather than referenced directly inside the DO body below.
SET tango_migration.migration_runner_password = :'migration_runner_password';
SET tango_migration.app_runtime_password = :'app_runtime_password';

DO $$
DECLARE
    migration_runner_password text := current_setting('tango_migration.migration_runner_password');
    app_runtime_password text := current_setting('tango_migration.app_runtime_password');
BEGIN
    IF current_user = 'migration_runner' THEN
        -- Already bootstrapped by a prior one-off superuser run; nothing left to do here.
        RETURN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'migration_runner') THEN
        EXECUTE format('CREATE ROLE migration_runner LOGIN PASSWORD %L', migration_runner_password);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_runtime') THEN
        EXECUTE format('CREATE ROLE app_runtime LOGIN PASSWORD %L', app_runtime_password);
    END IF;

    -- Let the connecting superuser reassign ownership below (ALTER ... OWNER TO requires
    -- membership in the target role unless already a superuser).
    EXECUTE format('GRANT migration_runner TO %I', current_user);

    EXECUTE 'GRANT CREATE, USAGE ON SCHEMA public TO migration_runner';
    EXECUTE 'ALTER SCHEMA public OWNER TO migration_runner';

    EXECUTE 'ALTER TABLE IF EXISTS game OWNER TO migration_runner';
    EXECUTE 'ALTER TABLE IF EXISTS round OWNER TO migration_runner';
    EXECUTE 'ALTER TABLE IF EXISTS artist OWNER TO migration_runner';
    EXECUTE 'ALTER TABLE IF EXISTS track OWNER TO migration_runner';
    EXECUTE 'ALTER TABLE IF EXISTS track_provider OWNER TO migration_runner';
    EXECUTE 'ALTER TABLE IF EXISTS question OWNER TO migration_runner';
    EXECUTE 'ALTER TABLE IF EXISTS guess_feedback OWNER TO migration_runner';
    EXECUTE 'ALTER TABLE IF EXISTS game_round OWNER TO migration_runner';
    EXECUTE 'ALTER TABLE IF EXISTS round_question OWNER TO migration_runner';
    EXECUTE 'ALTER VIEW IF EXISTS admin_question OWNER TO migration_runner';

    EXECUTE 'ALTER FUNCTION set_updated_at() OWNER TO migration_runner';
    EXECUTE 'ALTER FUNCTION is_uuid_jsonb_array(jsonb, integer, integer, boolean) OWNER TO migration_runner';
    EXECUTE 'ALTER FUNCTION validate_feedback_track_position() OWNER TO migration_runner';
    EXECUTE 'ALTER FUNCTION create_question_for_artist(integer, integer, uuid) OWNER TO migration_runner';
    EXECUTE 'ALTER FUNCTION create_random_question() OWNER TO migration_runner';

    EXECUTE 'GRANT USAGE ON SCHEMA public TO app_runtime';
END
$$;

-- Safe to run as either the superuser (first bootstrap) or migration_runner (every later
-- release): grants on objects that already exist, then matching default privileges so future
-- migrations don't need to remember to re-grant app_runtime access on every new table/function.
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO app_runtime;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO app_runtime;

ALTER DEFAULT PRIVILEGES FOR ROLE migration_runner IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE ON TABLES TO app_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE migration_runner IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO app_runtime;
