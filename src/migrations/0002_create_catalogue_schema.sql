CREATE SCHEMA IF NOT EXISTS catalogue;

CREATE TABLE IF NOT EXISTS catalogue.orchestra (
    id text PRIMARY KEY,
    display_name text NOT NULL,
    artist_id text NULL REFERENCES music.artist(id),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS catalogue.track_entry (
    id text PRIMARY KEY,
    orchestra_id text NOT NULL REFERENCES catalogue.orchestra(id),
    recording_id text NULL REFERENCES music.recording(id),
    title text NOT NULL,
    preview_url text NOT NULL,
    duration_ms integer NOT NULL CHECK (duration_ms > 0),
    is_usable boolean GENERATED ALWAYS AS (
        length(trim(preview_url)) > 0
        AND duration_ms BETWEEN 60000 AND 900000
    ) STORED,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (orchestra_id, preview_url)
);

CREATE UNIQUE INDEX IF NOT EXISTS track_entry_orchestra_recording_unique
    ON catalogue.track_entry (orchestra_id, recording_id)
    WHERE recording_id IS NOT NULL;
