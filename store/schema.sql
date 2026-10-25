-- Chiron app data (Postgres / Neon). LangGraph's checkpointer creates its own tables.
-- Idempotent: safe to run on every startup.

CREATE TABLE IF NOT EXISTS users (
    id          BIGSERIAL PRIMARY KEY,
    email       TEXT NOT NULL UNIQUE,
    name        TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One row per consultation; its id is also the LangGraph thread id.
CREATE TABLE IF NOT EXISTS consultations (
    id           TEXT PRIMARY KEY,
    user_id      BIGINT NOT NULL REFERENCES users(id),
    case_id      TEXT NOT NULL,
    mode         TEXT NOT NULL DEFAULT 'chat',
    started_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at  TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS consultations_user_idx ON consultations (user_id, started_at DESC);

-- Every message of a consultation, with what the agent did. Source for feedback,
-- per-student history and new eval datasets.
CREATE TABLE IF NOT EXISTS turns (
    consultation_id  TEXT NOT NULL REFERENCES consultations(id) ON DELETE CASCADE,
    n                INT NOT NULL,
    role             TEXT NOT NULL,          -- estudiante | paciente | docente
    text             TEXT NOT NULL,
    intent           TEXT,                   -- router decision (on the student's turn)
    facts            TEXT[],                 -- case facts the patient revealed
    exams            TEXT[],
    studies          TEXT[],
    latency_ms       INT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (consultation_id, n)
);
