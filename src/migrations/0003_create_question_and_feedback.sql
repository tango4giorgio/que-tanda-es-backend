-- Validates JSONB arrays of UUID strings without introducing element-level foreign keys.
CREATE OR REPLACE FUNCTION is_uuid_jsonb_array(
    value jsonb,
    minimum_length integer,
    maximum_length integer,
    require_distinct boolean DEFAULT true
)
RETURNS boolean
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    item text;
    item_count integer;
BEGIN
    IF jsonb_typeof(value) <> 'array' THEN
        RETURN false;
    END IF;
    item_count := jsonb_array_length(value);
    IF item_count < minimum_length OR item_count > maximum_length THEN
        RETURN false;
    END IF;
    FOR item IN SELECT jsonb_array_elements_text(value)
    LOOP
        PERFORM item::uuid;
    END LOOP;
    IF require_distinct AND (
        SELECT count(*) <> count(DISTINCT element)
        FROM jsonb_array_elements_text(value) AS element
    ) THEN
        RETURN false;
    END IF;
    RETURN true;
EXCEPTION
    WHEN invalid_text_representation THEN
        RETURN false;
END;
$$;

-- Existing gameplay data is disposable for this model transition. Rebuild only when the
-- previous scalar question schema is detected; catalogue tables are not touched.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'question'
          AND column_name = 'round_id'
    )
    THEN
        DROP TABLE IF EXISTS guess_feedback CASCADE;
        DROP TABLE IF EXISTS question_choice CASCADE;
        DROP TABLE IF EXISTS question CASCADE;
        ALTER TABLE round DROP COLUMN IF EXISTS question_id;
        TRUNCATE round, game RESTART IDENTITY CASCADE;
    END IF;
END;
$$;

-- One aggregate guess prompt per round. Track and artist arrays preserve gameplay order.
CREATE TABLE IF NOT EXISTS question (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    track_ids jsonb NOT NULL CHECK (is_uuid_jsonb_array(track_ids, 1, 3)),
    artist_ids jsonb NOT NULL CHECK (is_uuid_jsonb_array(artist_ids, 3, 3)),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

DROP TRIGGER IF EXISTS question_set_updated_at ON question;
CREATE TRIGGER question_set_updated_at
    BEFORE UPDATE ON question
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE INDEX IF NOT EXISTS question_track_ids_idx ON question USING gin (track_ids);
CREATE INDEX IF NOT EXISTS question_artist_ids_idx ON question USING gin (artist_ids);

DO $$
BEGIN
    IF to_regclass('public.round_question') IS NULL THEN
        ALTER TABLE round ADD COLUMN IF NOT EXISTS question_id uuid;
        ALTER TABLE round
            DROP CONSTRAINT IF EXISTS round_question_id_fkey,
            ADD CONSTRAINT round_question_id_fkey
                FOREIGN KEY (question_id) REFERENCES question (id);
        CREATE UNIQUE INDEX IF NOT EXISTS round_question_id_idx ON round (question_id);
        ALTER TABLE round ALTER COLUMN question_id SET NOT NULL;
    END IF;
END;
$$;

-- The outcome of one ordered track attempt within a question.
CREATE TABLE IF NOT EXISTS guess_feedback (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    question_id uuid NOT NULL REFERENCES question (id),
    track_position smallint NOT NULL CHECK (track_position BETWEEN 1 AND 3),
    guessed_artist_id uuid NULL REFERENCES artist (id),
    outcome text NOT NULL CHECK (outcome IN ('correct', 'wrong', 'skipped')),
    elapsed_ms integer NOT NULL CHECK (elapsed_ms BETWEEN 0 AND 30000),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (question_id, track_position),
    CHECK (
        (outcome = 'skipped' AND guessed_artist_id IS NULL)
        OR (outcome <> 'skipped' AND guessed_artist_id IS NOT NULL)
    )
);

CREATE OR REPLACE FUNCTION validate_feedback_track_position()
RETURNS trigger AS $$
DECLARE
    track_count integer;
BEGIN
    SELECT jsonb_array_length(track_ids)
      INTO track_count
      FROM question
     WHERE id = NEW.question_id;
    IF track_count IS NULL OR NEW.track_position > track_count THEN
        RAISE EXCEPTION 'track_position % is not present on question %',
            NEW.track_position, NEW.question_id
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS guess_feedback_validate_track_position ON guess_feedback;
CREATE TRIGGER guess_feedback_validate_track_position
    BEFORE INSERT OR UPDATE ON guess_feedback
    FOR EACH ROW
    EXECUTE FUNCTION validate_feedback_track_position();

DROP TRIGGER IF EXISTS guess_feedback_set_updated_at ON guess_feedback;
CREATE TRIGGER guess_feedback_set_updated_at
    BEFORE UPDATE ON guess_feedback
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();
