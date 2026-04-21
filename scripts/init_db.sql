CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS tickets (
    id              BIGSERIAL PRIMARY KEY,
    external_id     TEXT UNIQUE,
    source          TEXT NOT NULL,
    subject         TEXT NOT NULL,
    body            TEXT NOT NULL,
    requester_email TEXT,
    category        TEXT,
    priority        TEXT,
    sentiment       TEXT,
    status          TEXT NOT NULL DEFAULT 'open',
    draft_response  TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    triaged_at      TIMESTAMPTZ,
    resolved_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS tickets_category_idx ON tickets (category);
CREATE INDEX IF NOT EXISTS tickets_status_idx   ON tickets (status);
CREATE INDEX IF NOT EXISTS tickets_created_idx  ON tickets (created_at DESC);

CREATE TABLE IF NOT EXISTS kb_chunks (
    id          BIGSERIAL PRIMARY KEY,
    source_path TEXT NOT NULL,
    title       TEXT NOT NULL,
    category    TEXT NOT NULL,
    content     TEXT NOT NULL,
    embedding   vector(1536),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS kb_chunks_embed_idx
    ON kb_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX IF NOT EXISTS kb_chunks_category_idx ON kb_chunks (category);
