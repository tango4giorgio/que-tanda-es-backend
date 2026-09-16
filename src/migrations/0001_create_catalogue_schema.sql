CREATE SCHEMA IF NOT EXISTS catalogue;

CREATE TABLE IF NOT EXISTS catalogue.recording_provider (
    musicbrainz_recording_id uuid NOT NULL,
    provider text NOT NULL CHECK (length(trim(provider)) > 0),
    provider_url text NOT NULL CHECK (
        length(trim(provider_url)) > 0
        AND provider_url ~ '^https?://'
    ),
    duration_ms integer NULL CHECK (duration_ms IS NULL OR duration_ms > 0),
    is_usable boolean GENERATED ALWAYS AS (
        length(trim(provider_url)) > 0
        AND (duration_ms IS NULL OR duration_ms BETWEEN 60000 AND 900000)
    ) STORED,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (musicbrainz_recording_id, provider, provider_url),
    UNIQUE (provider, provider_url)
);
