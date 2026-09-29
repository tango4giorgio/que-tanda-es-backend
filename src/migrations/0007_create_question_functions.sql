-- Questions created through these helpers may expose a variable number of artist choices.
ALTER TABLE question
    DROP CONSTRAINT IF EXISTS question_artist_ids_check,
    DROP CONSTRAINT IF EXISTS question_artist_ids_valid;
ALTER TABLE question
    ADD CONSTRAINT question_artist_ids_valid
        CHECK (is_uuid_jsonb_array(artist_ids, 1, 2147483647));

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
