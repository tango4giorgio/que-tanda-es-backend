-- One-off application-database bootstrap. Run with the Supabase Postgres superuser; normal
-- releases must use migration_runner and must never receive this superuser connection.
--
-- Passwords are supplied as psql variables:
--   psql "$SUPERUSER_DATABASE_URL" \
--     --set ON_ERROR_STOP=1 \
--     -v migration_runner_password="$MIGRATION_RUNNER_PASSWORD" \
--     -v app_runtime_password="$APP_RUNTIME_PASSWORD" \
--     -f src/database/bootstrap/create_roles.sql

SET tango_bootstrap.migration_runner_password = :'migration_runner_password';
SET tango_bootstrap.app_runtime_password = :'app_runtime_password';

DO $bootstrap$
DECLARE
    migration_password text :=
        current_setting('tango_bootstrap.migration_runner_password');
    runtime_password text :=
        current_setting('tango_bootstrap.app_runtime_password');
    database_object record;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'migration_runner') THEN
        CREATE ROLE migration_runner LOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_runtime') THEN
        CREATE ROLE app_runtime LOGIN;
    END IF;

    EXECUTE format(
        'ALTER ROLE migration_runner NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD %L',
        migration_password
    );
    EXECUTE format(
        'ALTER ROLE app_runtime NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD %L',
        runtime_password
    );

    EXECUTE format('GRANT migration_runner TO %I', current_user);

    REVOKE CREATE ON SCHEMA public FROM PUBLIC;
    GRANT CREATE, USAGE ON SCHEMA public TO migration_runner;
    GRANT USAGE ON SCHEMA public TO app_runtime;
    ALTER SCHEMA public OWNER TO migration_runner;

    -- Supports an existing database that was created before role separation. On a fresh
    -- database these loops are empty and future objects are owned by migration_runner because
    -- all versioned migrations connect as that role.
    FOR database_object IN
        SELECT
            c.relkind,
            n.nspname AS schema_name,
            c.relname AS object_name
        FROM pg_class AS c
        JOIN pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind IN ('r', 'p', 'S', 'v', 'm')
    LOOP
        EXECUTE format(
            'ALTER %s %I.%I OWNER TO migration_runner',
            CASE database_object.relkind
                WHEN 'S' THEN 'SEQUENCE'
                WHEN 'v' THEN 'VIEW'
                WHEN 'm' THEN 'MATERIALIZED VIEW'
                ELSE 'TABLE'
            END,
            database_object.schema_name,
            database_object.object_name
        );
    END LOOP;

    FOR database_object IN
        SELECT
            n.nspname AS schema_name,
            p.proname AS object_name,
            pg_get_function_identity_arguments(p.oid) AS identity_arguments,
            p.prokind
        FROM pg_proc AS p
        JOIN pg_namespace AS n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public'
          AND p.prokind IN ('f', 'p')
    LOOP
        EXECUTE format(
            'ALTER %s %I.%I(%s) OWNER TO migration_runner',
            CASE database_object.prokind
                WHEN 'p' THEN 'PROCEDURE'
                ELSE 'FUNCTION'
            END,
            database_object.schema_name,
            database_object.object_name,
            database_object.identity_arguments
        );
    END LOOP;
END
$bootstrap$;

GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO app_runtime;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_runtime;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO app_runtime;

DO $bootstrap$
BEGIN
    IF to_regclass('public.schema_migration') IS NOT NULL THEN
        REVOKE ALL ON TABLE public.schema_migration FROM app_runtime;
    END IF;
END
$bootstrap$;

ALTER DEFAULT PRIVILEGES FOR ROLE migration_runner IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE ON TABLES TO app_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE migration_runner IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO app_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE migration_runner IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO app_runtime;

RESET tango_bootstrap.migration_runner_password;
RESET tango_bootstrap.app_runtime_password;
