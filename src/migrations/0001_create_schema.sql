-- Fresh-database bootstrap for the tango game. This file defines the final data model directly;
-- it intentionally contains no historical schema-transition or data-migration logic.

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

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

CREATE TABLE IF NOT EXISTS game (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS round (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS artist (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name text NOT NULL CHECK (length(trim(display_name)) > 0),
    external_ids jsonb NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS track (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    artist_id uuid NOT NULL REFERENCES artist (id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

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

CREATE TABLE IF NOT EXISTS question (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    track_ids jsonb NOT NULL CHECK (is_uuid_jsonb_array(track_ids, 1, 3)),
    artist_ids jsonb NOT NULL
        CHECK (is_uuid_jsonb_array(artist_ids, 1, 2147483647)),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

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

CREATE TABLE IF NOT EXISTS game_round (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    game_id uuid NOT NULL REFERENCES game (id),
    round_id uuid NOT NULL REFERENCES round (id),
    sequence_number smallint NOT NULL CHECK (sequence_number BETWEEN 1 AND 3),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (game_id, round_id),
    UNIQUE (game_id, sequence_number)
);

CREATE TABLE IF NOT EXISTS round_question (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    round_id uuid NOT NULL REFERENCES round (id),
    question_id uuid NOT NULL REFERENCES question (id),
    sequence_number smallint NOT NULL CHECK (sequence_number > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (round_id, question_id),
    UNIQUE (round_id, sequence_number)
);

CREATE INDEX IF NOT EXISTS track_artist_id_idx ON track (artist_id);
CREATE INDEX IF NOT EXISTS track_provider_track_id_idx ON track_provider (track_id);
CREATE INDEX IF NOT EXISTS question_track_ids_idx ON question USING gin (track_ids);
CREATE INDEX IF NOT EXISTS question_artist_ids_idx ON question USING gin (artist_ids);
CREATE INDEX IF NOT EXISTS game_round_round_id_idx ON game_round (round_id);
CREATE INDEX IF NOT EXISTS round_question_question_id_idx ON round_question (question_id);

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

DROP TRIGGER IF EXISTS game_set_updated_at ON game;
CREATE TRIGGER game_set_updated_at
    BEFORE UPDATE ON game FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS round_set_updated_at ON round;
CREATE TRIGGER round_set_updated_at
    BEFORE UPDATE ON round FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS artist_set_updated_at ON artist;
CREATE TRIGGER artist_set_updated_at
    BEFORE UPDATE ON artist FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS track_set_updated_at ON track;
CREATE TRIGGER track_set_updated_at
    BEFORE UPDATE ON track FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS track_provider_set_updated_at ON track_provider;
CREATE TRIGGER track_provider_set_updated_at
    BEFORE UPDATE ON track_provider FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS question_set_updated_at ON question;
CREATE TRIGGER question_set_updated_at
    BEFORE UPDATE ON question FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS guess_feedback_validate_track_position ON guess_feedback;
CREATE TRIGGER guess_feedback_validate_track_position
    BEFORE INSERT OR UPDATE ON guess_feedback
    FOR EACH ROW EXECUTE FUNCTION validate_feedback_track_position();
DROP TRIGGER IF EXISTS guess_feedback_set_updated_at ON guess_feedback;
CREATE TRIGGER guess_feedback_set_updated_at
    BEFORE UPDATE ON guess_feedback FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS game_round_set_updated_at ON game_round;
CREATE TRIGGER game_round_set_updated_at
    BEFORE UPDATE ON game_round FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS round_question_set_updated_at ON round_question;
CREATE TRIGGER round_question_set_updated_at
    BEFORE UPDATE ON round_question FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE FUNCTION create_question_for_artist(
    number_of_tracks integer,
    number_of_choices integer,
    artist_id uuid
)
RETURNS question
LANGUAGE plpgsql
VOLATILE
AS $$
DECLARE
    selected_track_ids jsonb;
    selected_artist_ids jsonb;
    created_question question;
BEGIN
    IF number_of_tracks NOT BETWEEN 1 AND 3 THEN
        RAISE EXCEPTION 'number_of_tracks must be between 1 and 3'
            USING ERRCODE = '22023';
    END IF;
    IF number_of_choices < 1 THEN
        RAISE EXCEPTION 'number_of_choices must be at least 1'
            USING ERRCODE = '22023';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM artist WHERE id = artist_id) THEN
        RAISE EXCEPTION 'artist % does not exist', artist_id
            USING ERRCODE = '22023';
    END IF;

    SELECT jsonb_agg(candidate.id)
      INTO selected_track_ids
      FROM (
          SELECT t.id
          FROM track AS t
          JOIN track_provider AS tp ON tp.track_id = t.id
          WHERE t.artist_id = create_question_for_artist.artist_id
          GROUP BY t.id
          ORDER BY random()
          LIMIT number_of_tracks
      ) AS candidate;

    IF COALESCE(jsonb_array_length(selected_track_ids), 0) <> number_of_tracks THEN
        RAISE EXCEPTION 'artist % does not have % tracks with providers',
            artist_id, number_of_tracks
            USING ERRCODE = '22023';
    END IF;

    SELECT jsonb_agg(candidate.id)
      INTO selected_artist_ids
      FROM (
          WITH distractors AS (
              SELECT a.id
              FROM artist AS a
              WHERE a.id <> create_question_for_artist.artist_id
                AND EXISTS (
                    SELECT 1
                    FROM track AS t
                    JOIN track_provider AS tp ON tp.track_id = t.id
                    WHERE t.artist_id = a.id
                )
              ORDER BY random()
              LIMIT number_of_choices - 1
          ),
          selected AS (
                SELECT create_question_for_artist.artist_id AS id
                UNION ALL
                SELECT id FROM distractors
          )
          SELECT selected.id
          FROM selected
          ORDER BY random()
      ) AS candidate;

    IF COALESCE(jsonb_array_length(selected_artist_ids), 0) <> number_of_choices THEN
        RAISE EXCEPTION 'only % eligible artists are available for % choices',
            COALESCE(jsonb_array_length(selected_artist_ids), 0), number_of_choices
            USING ERRCODE = '22023';
    END IF;

    INSERT INTO question (track_ids, artist_ids)
    VALUES (selected_track_ids, selected_artist_ids)
    RETURNING * INTO created_question;

    RETURN created_question;
END;
$$;

CREATE OR REPLACE FUNCTION create_random_question()
RETURNS question
LANGUAGE plpgsql
VOLATILE
AS $$
DECLARE
    selected_artist_id uuid;
BEGIN
    SELECT a.id
      INTO selected_artist_id
      FROM artist AS a
     WHERE (
         SELECT count(DISTINCT t.id)
         FROM track AS t
         JOIN track_provider AS tp ON tp.track_id = t.id
         WHERE t.artist_id = a.id
     ) >= 3
     ORDER BY random()
     LIMIT 1;

    IF selected_artist_id IS NULL THEN
        RAISE EXCEPTION 'no artist has at least 3 tracks with providers'
            USING ERRCODE = '22023';
    END IF;

    RETURN create_question_for_artist(3, 3, selected_artist_id);
END;
$$;

CREATE OR REPLACE VIEW admin_question AS
SELECT
    q.id AS question_id,
    track_details.tracks,
    artist_details.artists,
    correct_artist.id AS correct_artist_id,
    correct_artist.display_name AS correct_artist_name,
    q.created_at,
    q.updated_at
FROM question AS q
CROSS JOIN LATERAL (
    SELECT
        jsonb_agg(
            jsonb_build_object('trackId', t.id, 'title', preferred_provider.title)
            ORDER BY track_entry.position
        ) AS tracks,
        (array_agg(t.artist_id ORDER BY track_entry.position))[1] AS correct_artist_id
    FROM jsonb_array_elements_text(q.track_ids)
        WITH ORDINALITY AS track_entry(track_id, position)
    JOIN track AS t ON t.id = track_entry.track_id::uuid
    LEFT JOIN LATERAL (
        SELECT tp.title
        FROM track_provider AS tp
        WHERE tp.track_id = t.id
          AND tp.title IS NOT NULL
        ORDER BY (tp.provider = 'deezer') DESC, tp.provider, tp.id
        LIMIT 1
    ) AS preferred_provider ON true
) AS track_details
CROSS JOIN LATERAL (
    SELECT jsonb_agg(
        jsonb_build_object('artistId', a.id, 'name', a.display_name)
        ORDER BY artist_entry.position
    ) AS artists
    FROM jsonb_array_elements_text(q.artist_ids)
        WITH ORDINALITY AS artist_entry(artist_id, position)
    JOIN artist AS a ON a.id = artist_entry.artist_id::uuid
) AS artist_details
JOIN artist AS correct_artist ON correct_artist.id = track_details.correct_artist_id;
