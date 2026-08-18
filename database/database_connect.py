import os
import logging
import psycopg

from datetime import datetime
from contextlib import contextmanager

from pgvector.psycopg import register_vector_async

@contextmanager
def with_transaction(conn):
    try:
        with conn.cursor() as cursor:
            yield cursor
        conn.commit()

    except:
        conn.rollback()
        raise

    finally:
        conn.close()


def _log_connection_status(conn):
    logger = logging.getLogger("database_connect")
    logger.setLevel(logging.INFO)

    offset = datetime.now().astimezone().utcoffset()
    hours = int(offset.total_seconds() // 3600)

    logger.info(
        "Postgres connection established\tBackend PID: %s\tDB Timzone: %+03d",
        conn.info.backend_pid,
        hours
    )


async def database_connect_async(*, host, port, dbname, user, password):
    conn = await psycopg.AsyncConnection.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password
    )

    await register_vector_async(conn)

    _log_connection_status(conn)

    return conn


def database_connect(*, host, port, dbname, user, password):
    conn = psycopg.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password
    )

    _log_connection_status(conn)

    return conn
