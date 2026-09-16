CREATE TABLE IF NOT EXISTS catalogue.musicbrainz_recording_cache (
    musicbrainz_recording_id uuid PRIMARY KEY,
    answer_artist_id uuid,
    answer_artist_name text,
    metadata_status text NOT NULL CHECK (
        metadata_status IN ('eligible', 'ambiguous_credit', 'not_found', 'error')
    ),
    source_updated_at timestamptz,
    fetched_at timestamptz NOT NULL,
    payload_hash text NOT NULL CHECK (length(trim(payload_hash)) > 0),
    CHECK (
        (metadata_status = 'eligible'
            AND answer_artist_id IS NOT NULL
            AND length(trim(answer_artist_name)) > 0)
        OR metadata_status <> 'eligible'
    )
);

CREATE INDEX IF NOT EXISTS musicbrainz_recording_cache_eligible_artist_idx
    ON catalogue.musicbrainz_recording_cache (answer_artist_id)
    WHERE metadata_status = 'eligible';

CREATE INDEX IF NOT EXISTS musicbrainz_recording_cache_fetched_idx
    ON catalogue.musicbrainz_recording_cache (fetched_at);
