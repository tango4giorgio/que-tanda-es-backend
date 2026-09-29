-- A canonical performer/orchestra, reusable across any number of games/questions.
CREATE TABLE IF NOT EXISTS artist (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name text NOT NULL CHECK (length(trim(display_name)) > 0),
    external_ids jsonb NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

DROP TRIGGER IF EXISTS artist_set_updated_at ON artist;
CREATE TRIGGER artist_set_updated_at
    BEFORE UPDATE ON artist
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

-- A canonical playable recording, reusable across any number of games/questions. Not keyed by
-- any external identifier (research.md §2); external source identifiers are recorded on
-- `track_provider` (`provider`, `provider_track_id`) instead.
CREATE TABLE IF NOT EXISTS track (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    artist_id uuid NOT NULL REFERENCES artist (id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

DROP TRIGGER IF EXISTS track_set_updated_at ON track;
CREATE TRIGGER track_set_updated_at
    BEFORE UPDATE ON track
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

-- Supports finding all tracks belonging to a given artist during round selection.
CREATE INDEX IF NOT EXISTS track_artist_id_idx
    ON track (artist_id);

-- A specific playable source for a track. No eligibility/usability flag is persisted (out of
-- scope). Stores the provider's own identifier for the track rather than a static URL, since
-- provider URLs can expire (research.md §7); a playable URL is resolved from
-- (provider, provider_track_id) at serving time.
CREATE TABLE IF NOT EXISTS track_provider (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    track_id uuid NOT NULL REFERENCES track (id),
    provider text NOT NULL CHECK (length(trim(provider)) > 0),
    provider_track_id text NOT NULL CHECK (length(trim(provider_track_id)) > 0),
    title text NULL CHECK (title IS NULL OR length(trim(title)) > 0),
    duration_ms integer NULL CHECK (duration_ms IS NULL OR duration_ms > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (track_id, provider, provider_track_id)
);

DROP TRIGGER IF EXISTS track_provider_set_updated_at ON track_provider;
CREATE TRIGGER track_provider_set_updated_at
    BEFORE UPDATE ON track_provider
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

-- Supports resolving all providers for a track at round-selection time.
CREATE INDEX IF NOT EXISTS track_provider_track_id_idx
    ON track_provider (track_id);
