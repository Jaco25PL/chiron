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

-- Where a turn's latency went, in ms: router, the node that answered, graph (nodes + checkpoint),
-- and later tts_first / tts_total for the patient's voice. Added after the table, hence ALTER.
ALTER TABLE turns ADD COLUMN IF NOT EXISTS timings JSONB;

-- RAG: course material chunks with gemini-embedding-001 vectors truncated to 768 dims
-- (Matryoshka; ~same top-5 as 3072 dims). Loaded by rag/to_pgvector.py.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS rag_chunks (
    id         TEXT PRIMARY KEY,
    materia    TEXT NOT NULL,
    tipo       TEXT NOT NULL,
    fuente     TEXT NOT NULL,
    seccion    TEXT,
    pagina     INT,
    texto      TEXT NOT NULL,
    metadata   JSONB NOT NULL,
    embedding  vector(768) NOT NULL
);
CREATE INDEX IF NOT EXISTS rag_chunks_embedding_idx ON rag_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS rag_chunks_materia_tipo_idx ON rag_chunks (materia, tipo);

-- Human review of the LLM judge (store/review.py). `item` is what the reviewer sees; `juez`
-- holds the judge's verdict, kept apart so the page never shows it.
CREATE TABLE IF NOT EXISTS review_items (
    id     TEXT PRIMARY KEY,
    orden  INT NOT NULL,
    item   JSONB NOT NULL,
    juez   JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS review_labels (
    item_id     TEXT NOT NULL REFERENCES review_items(id) ON DELETE CASCADE,
    reviewer    TEXT NOT NULL,
    etiquetas   JSONB NOT NULL,          -- {criterio: true | false | null}
    nota        TEXT NOT NULL DEFAULT '',
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (item_id, reviewer)
);

-- Difficulty level (agents/grilla.py LEVELS): "principiante" shows the grilla checklist during the
-- consultation. Added after the table existed, hence the idempotent ALTER.
ALTER TABLE consultations ADD COLUMN IF NOT EXISTS nivel TEXT NOT NULL DEFAULT 'normal';
