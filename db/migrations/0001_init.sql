-- migrate:up

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS messages (
    id BIGSERIAL PRIMARY KEY,
    role TEXT NOT NULL,
    gateway TEXT NOT NULL,
    direction TEXT NOT NULL,

    text_content TEXT,
    file_content TEXT,
    file_name TEXT,

    external_chat_id TEXT,
    external_user_id TEXT,
    external_user_name TEXT,
    external_message_id TEXT,

    llm_response JSONB,
    attributes JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at TIMESTAMPTZ DEFAULT NULL,
    resolved_at TIMESTAMPTZ DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    gateway TEXT NOT NULL,
    external_chat_id TEXT NOT NULL,
    external_user_id TEXT NOT NULL,
    external_user_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (gateway, external_chat_id, external_user_id)
);

CREATE TABLE IF NOT EXISTS user_cvs (
    id BIGSERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector(384),
    user_id BIGINT NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS documents (
    id BIGSERIAL PRIMARY KEY,
    source TEXT,
    provider TEXT,
    document JSONB,
    embedding vector(384),
    call_id TEXT NOT NULL,
    user_id BIGINT NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- migrate:down

DROP TABLE IF EXISTS documents;
DROP TABLE IF EXISTS user_cvs;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS messages;
DROP EXTENSION IF EXISTS vector;
