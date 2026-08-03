import os
import logging
import psycopg

from datetime import datetime

logger = logging.getLogger("db_connect")
logger.setLevel(logging.INFO)

def _log_connection_status(conn):
    offset = datetime.now().astimezone().utcoffset()
    hours = int(offset.total_seconds() // 3600)

    logger.info(
        "Postgres connection established\tBackend PID: %s\tDB Timzone: %+03d",
        conn.info.backend_pid,
        hours
    )


def database_connect(*, host, dbname, user, password):
    conn = psycopg.connect(
        host=host,
        dbname=dbname,
        user=user,
        password=password
    )

    _log_connection_status(conn)

    return conn


async def database_connect_async(*, host, dbname, user, password):
    conn = await psycopg.AsyncConnection.connect(
        host=host,
        dbname=dbname,
        user=user,
        password=password
    )

    _log_connection_status(conn)

    return conn


def create_table_messages(conn):

    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id BIGSERIAL PRIMARY KEY,
                    role TEXT NOT NULL,
                    gateway TEXT NOT NULL,
                    direction TEXT NOT NULL,

                    text_content TEXT,
                    file_content TEXT,

                    external_chat_id TEXT,
                    external_user_id TEXT,
                    external_user_name TEXT,
                    external_message_id TEXT,

                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    processed_at TIMESTAMPTZ DEFAULT NULL,
                    resolved_at TIMESTAMPTZ DEFAULT NULL
                )
            """)

        conn.commit()

    finally:
        conn.close()

def drop_table_messages(conn):
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                DROP TABLE IF EXISTS messages
            """)

        conn.commit()

    finally:
        conn.close()


# TABLE SEARCHES

def create_table_searches():
    raise NotImplementedError()

def drop_table_searches():
    raise NotImplementedError()


# INDEX

# Todo: init INDEX - когда подключу графану
#   CREATE INDEX IF NOT EXISTS idx_messages_queue
#   ON messages (role, processed, id);

def create_index_on_messages():
    raise NotImplementedError()

def drop_index_on_messages():
    raise NotImplementedError()
