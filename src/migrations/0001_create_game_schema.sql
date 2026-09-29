-- Shared trigger function that keeps `updated_at` current on every table in this schema
-- (research.md §6). Attached per-table below and in the migrations that follow.
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- A played session: purely a grouping of rounds, with no status field (2026-09-24
-- clarification). Whether it reached a full session is inferred from COUNT(round).
CREATE TABLE IF NOT EXISTS game (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

DROP TRIGGER IF EXISTS game_set_updated_at ON game;
CREATE TRIGGER game_set_updated_at
    BEFORE UPDATE ON game
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

-- One round played within a game.
CREATE TABLE IF NOT EXISTS round (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    game_id uuid NOT NULL REFERENCES game (id),
    sequence_number smallint NOT NULL CHECK (sequence_number BETWEEN 1 AND 3),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (game_id, sequence_number)
);

DROP TRIGGER IF EXISTS round_set_updated_at ON round;
CREATE TRIGGER round_set_updated_at
    BEFORE UPDATE ON round
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

-- Supports reconstructing a game's rounds in play order (User Story 1, SC-001) and cheaply
-- counting a game's existing rounds during round selection (research.md §4/§5).
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
        CREATE INDEX IF NOT EXISTS round_game_id_sequence_number_idx
            ON round (game_id, sequence_number);
    END IF;
END;
$$;
