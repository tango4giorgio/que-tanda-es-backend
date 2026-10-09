-- Adds session tracking (feature 021-backend-session-tracking). A session is a standalone
-- row correlated with gameplay requests only via the `X-Session-Id` header; no foreign-key
-- relationship to `game`/`round`/`question`/`guess_feedback` is required (data-model.md).

CREATE TABLE IF NOT EXISTS session (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at timestamptz NOT NULL DEFAULT now(),
    last_interaction_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (last_interaction_at >= started_at)
);

DROP TRIGGER IF EXISTS session_set_updated_at ON session;
CREATE TRIGGER session_set_updated_at
    BEFORE UPDATE ON session FOR EACH ROW EXECUTE FUNCTION set_updated_at();
