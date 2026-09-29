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

DROP TRIGGER IF EXISTS game_round_set_updated_at ON game_round;
CREATE TRIGGER game_round_set_updated_at
    BEFORE UPDATE ON game_round
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE INDEX IF NOT EXISTS game_round_round_id_idx ON game_round (round_id);

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

DROP TRIGGER IF EXISTS round_question_set_updated_at ON round_question;
CREATE TRIGGER round_question_set_updated_at
    BEFORE UPDATE ON round_question
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE INDEX IF NOT EXISTS round_question_question_id_idx
    ON round_question (question_id);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'round'
          AND column_name = 'game_id'
    )
    THEN
        INSERT INTO game_round (
            game_id, round_id, sequence_number, created_at, updated_at
        )
        SELECT game_id, id, sequence_number, created_at, updated_at
        FROM round
        ON CONFLICT (game_id, round_id) DO NOTHING;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'round'
          AND column_name = 'question_id'
    )
    THEN
        INSERT INTO round_question (
            round_id, question_id, sequence_number, created_at, updated_at
        )
        SELECT id, question_id, 1, created_at, updated_at
        FROM round
        ON CONFLICT (round_id, question_id) DO NOTHING;
    END IF;
END;
$$;

DROP INDEX IF EXISTS round_game_id_sequence_number_idx;
DROP INDEX IF EXISTS round_question_id_idx;

ALTER TABLE round
    DROP COLUMN IF EXISTS game_id,
    DROP COLUMN IF EXISTS question_id,
    DROP COLUMN IF EXISTS sequence_number;
