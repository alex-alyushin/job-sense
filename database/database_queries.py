
# TABLE MESSAGES

def init_messages(cursor):
    cursor.execute("""
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

            attributes JSONB,

            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            processed_at TIMESTAMPTZ DEFAULT NULL,
            resolved_at TIMESTAMPTZ DEFAULT NULL
        )
    """)


def drop_messages(cursor):
    cursor.execute("DROP TABLE IF EXISTS messages")


# EXTENSION VECTOR

def init_vector(cursor):
    cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")


# TABLE DOCUMENTS

def init_documents(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id BIGSERIAL PRIMARY KEY,
            source TEXT,
            provider TEXT,
            document JSONB,
            embedding vector(384),
            search_initiator BIGINT NOT NULL REFERENCES messages(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)


def drop_documents(cursor):
    cursor.execute("DROP TABLE IF EXISTS documents")


# INDEX

def init_index():
    raise NotImplementedError()

def drop_index():
    raise NotImplementedError()
