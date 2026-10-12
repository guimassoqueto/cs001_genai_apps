-- Applied at startup; every statement is idempotent.

-- Conversation memory: one row per user message. `replies` maps model id -> that model's
-- analysis (JSON), so in an A/B turn each model can be shown its own earlier answer.
CREATE TABLE IF NOT EXISTS conversation_turns (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT    NOT NULL,
    user_message    TEXT    NOT NULL,
    replies         TEXT    NOT NULL,
    created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_turns_conversation ON conversation_turns (conversation_id, id);

-- A/B test runs: the same message sent to several models.
CREATE TABLE IF NOT EXISTS comparisons (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    winner          TEXT,
    voted_at        TEXT,
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS comparison_results (
    comparison_id TEXT    NOT NULL REFERENCES comparisons (id) ON DELETE CASCADE,
    model         TEXT    NOT NULL,
    ok            INTEGER NOT NULL,
    error_code    TEXT,
    duration      REAL    NOT NULL,
    cached        INTEGER NOT NULL,
    input_tokens  INTEGER,
    output_tokens INTEGER,
    PRIMARY KEY (comparison_id, model)
);
