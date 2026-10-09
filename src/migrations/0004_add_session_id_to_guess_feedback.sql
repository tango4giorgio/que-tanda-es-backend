-- Alters guess_feedback for the 021-backend-session-tracking follow-up:
--  1. Adds session_id so a recorded guess/skip outcome can be traced back to the submitting
--     session. This is a plain, unconstrained identifier rather than a foreign key:
--     guess_feedback intentionally has no relationship to the session table, so the column is
--     nullable and carries no referential integrity constraint.
--  2. Widens elapsed_ms from integer to numeric(10, 3) (decimal) so fractional timings
--     can be recorded. The existing `BETWEEN 0 AND 30000` bound is preserved.

ALTER TABLE guess_feedback
    ADD COLUMN IF NOT EXISTS session_id uuid;

ALTER TABLE guess_feedback
    ALTER COLUMN elapsed_ms TYPE numeric(10, 3);

