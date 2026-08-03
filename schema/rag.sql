-- RAG Q&A layer schema (Extension 1)
-- Run via: psql $DATABASE_URL -f schema/rag.sql
--
-- Stores natural-language documents generated from the NFL database along with
-- their OpenAI embeddings (text-embedding-3-small → 1536 dims) for cosine
-- similarity retrieval. Idempotent: safe to run multiple times.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id          BIGSERIAL PRIMARY KEY,
    doc_type    VARCHAR(30) NOT NULL,        -- player_season | game_recap | leaderboard
    ref_id      VARCHAR(60) NOT NULL,        -- e.g. "00-0034796:2024" or game_id
    content     TEXT        NOT NULL,        -- the natural-language document
    embedding   vector(1536),               -- OpenAI text-embedding-3-small
    metadata    JSONB       DEFAULT '{}'::jsonb,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (doc_type, ref_id)
);

-- HNSW index for fast cosine-distance nearest-neighbor search.
CREATE INDEX IF NOT EXISTS idx_documents_embedding
    ON documents USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_documents_doc_type ON documents (doc_type);
