CREATE SCHEMA IF NOT EXISTS feedback;

CREATE TABLE IF NOT EXISTS feedback.guess_attempt (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    round_token text NOT NULL CHECK (length(trim(round_token)) > 0),
    track_position smallint NOT NULL CHECK (track_position BETWEEN 1 AND 3),
    recording_id uuid NOT NULL,
    correct_artist_id uuid NOT NULL,
    guessed_artist_id uuid NULL,
    outcome text NOT NULL CHECK (outcome IN ('correct', 'wrong', 'skipped')),
    elapsed_ms integer NOT NULL CHECK (elapsed_ms BETWEEN 0 AND 30000),
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (
        (outcome = 'skipped' AND guessed_artist_id IS NULL)
        OR (outcome <> 'skipped' AND guessed_artist_id IS NOT NULL)
    )
);

-- Supports SC-004's per-artist difficulty aggregation (accuracy rate and average
-- elapsed time grouped by correct_artist_id).
CREATE INDEX IF NOT EXISTS guess_attempt_correct_artist_idx
    ON feedback.guess_attempt (correct_artist_id);

-- Supports SC-004's per-track-position aggregation.
CREATE INDEX IF NOT EXISTS guess_attempt_track_position_idx
    ON feedback.guess_attempt (track_position);

-- Supports grouping all attempts belonging to the same round (User Story 3).
CREATE INDEX IF NOT EXISTS guess_attempt_round_token_idx
    ON feedback.guess_attempt (round_token);
