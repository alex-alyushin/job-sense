
# EXTENSION VECTOR

def init_vector(cursor):
    cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")


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

            llm_response JSONB,
            attributes JSONB,

            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            processed_at TIMESTAMPTZ DEFAULT NULL,
            resolved_at TIMESTAMPTZ DEFAULT NULL
        )
    """)


def drop_messages(cursor):
    cursor.execute("DROP TABLE IF EXISTS messages")


# INDEX

def init_messages_index(cursor):
    raise NotImplementedError()


def drop_messages_index(cursor):
    raise NotImplementedError()



# TABLE USERS

def init_users(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id BIGSERIAL PRIMARY KEY,
            gateway TEXT NOT NULL,
            external_chat_id TEXT NOT NULL,
            external_user_id TEXT NOT NULL,
            external_user_name TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (gateway, external_chat_id, external_user_id)
        )
    """)

def drop_users(cursor):
    cursor.execute("DROP TABLE IF EXISTS users")


# TABLE DOCUMENTS

def init_documents(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id BIGSERIAL PRIMARY KEY,
            source TEXT,
            provider TEXT,
            document JSONB,
            embedding vector(384),
            call_id TEXT NOT NULL,
            user_id BIGINT NOT NULL REFERENCES users(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)


def drop_documents(cursor):
    cursor.execute("DROP TABLE IF EXISTS documents")


# TABLE USER CVs

def init_user_cvs(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_cvs (
            id BIGSERIAL PRIMARY KEY,
            content TEXT NOT NULL,
            embedding vector(384),
            user_id BIGINT NOT NULL REFERENCES users(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)


def drop_user_cvs(cursor):
    cursor.execute("DROP TABLE IF EXISTS user_cvs")
