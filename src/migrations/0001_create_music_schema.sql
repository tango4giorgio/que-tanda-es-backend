CREATE SCHEMA IF NOT EXISTS music;

CREATE TABLE IF NOT EXISTS music.artist (
    id text PRIMARY KEY,
    name text NOT NULL,
    mbid_known boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS music.recording (
    id text PRIMARY KEY,
    artist_id text NOT NULL REFERENCES music.artist(id),
    title text NOT NULL,
    mbid_known boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);
