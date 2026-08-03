import json
import logging

from psycopg import sql, AsyncCursor
from psycopg.types.json import Jsonb

from contextlib import asynccontextmanager

from store.message_entity import MessageEntity, row_to_message
from store.document_entity import DocumentEntity, row_to_document

from database.database_connect import database_connect_async

from utils.utils import truncate

class MessagesStore:

    def __init__(self):
        self.logger = logging.getLogger("store")
        self.logger.setLevel(logging.INFO)
        self.conn_notify = None
        self.conn_listen = None
        self.conn_silent = None


    async def close(self):
        await self.conn_notify.close()
        await self.conn_listen.close()
        await self.conn_silent.close()


    async def __aenter__(self):
        return self


    async def __aexit__(self, exc_type, exc, tb):
        await self.close()
    

    @asynccontextmanager
    async def _with_transaction(self, conn):
        try:
            async with conn.cursor() as cursor:
                yield cursor
            await conn.commit()
        except:
            await conn.rollback()
            raise


    @classmethod
    async def create(cls, *, host, port, dbname, user, password):
        ctx = cls()

        ctx.conn_notify = await database_connect_async(
            host=host, port=port, dbname=dbname, user=user, password=password
        )

        ctx.conn_listen = await database_connect_async(
            host=host, port=port, dbname=dbname, user=user, password=password
        )

        ctx.conn_silent = await database_connect_async(
            host=host, port=port, dbname=dbname, user=user, password=password
        )

        return ctx


    async def store(
        self, role, gateway, direction,
        text_content=None, file_content=None, file_name=None,
        external_chat_id=None, external_user_id=None,
        external_user_name=None, external_message_id=None,
        attributes=None,
    ):
        """
        Store a message in the database and notify listeners.

        The message is inserted into the `messages` table and a PostgreSQL
        notification is sent to the channel `channel:{gateway}:{direction}`.
        """

        async with self._with_transaction(conn=self.conn_notify) as cursor:
            await cursor.execute("""
                INSERT INTO messages (
                    role,
                    gateway,
                    direction,
                    text_content,
                    file_content,
                    file_name,
                    external_chat_id,
                    external_user_id,
                    external_user_name,
                    external_message_id,
                    attributes
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                role,
                gateway,
                direction,
                text_content,
                file_content,
                file_name,
                external_chat_id,
                external_user_id,
                external_user_name,
                external_message_id,
                Jsonb(attributes) if attributes is not None else None,
            ))

            self._log_store_access(
                "Store",
                role=role,
                gateway=gateway,
                direction=direction,
                text_content=text_content,
                file_content=file_content,
                file_name=file_name,
            )

            await cursor.execute(
                sql.SQL("NOTIFY {}").format(
                    sql.Identifier(f"channel:{gateway}:{direction}")
                )
            )


    async def listen(self, gateway, direction, listener):
        """
        Listen for new messages and process them with the given listener.

        Subscribes to the PostgreSQL notification channel `channel:{gateway}:{direction}`.
        When a notification is received, unprocessed messages
        are loaded from the database and passed to the listener one by one.
        Each successfully processed message is marked as processed.
        """

        await self.conn_listen.execute(
            sql.SQL("LISTEN {}").format(
                sql.Identifier(f"channel:{gateway}:{direction}")
            )
        )

        await self.conn_listen.commit()

        async for _ in self.conn_listen.notifies():
            while True:
                async with self._with_transaction(conn=self.conn_notify) as cursor:
                    await cursor.execute("""
                        SELECT
                            id,
                            role,
                            gateway,
                            direction,
                            text_content,
                            file_content,
                            file_name,
                            external_chat_id,
                            external_user_id,
                            external_user_name,
                            external_message_id,
                            attributes,
                            created_at,
                            processed_at,
                            resolved_at
                        FROM messages
                        WHERE processed_at IS NULL AND direction = %s
                        ORDER BY id
                        LIMIT 1
                        FOR UPDATE SKIP LOCKED
                    """, (direction,))

                    row = await cursor.fetchone()

                    if row is None:
                        break

                    message = row_to_message(row)

                    self._log_store_access(
                        "Load",
                        role=message.role,
                        gateway=message.gateway,
                        direction=direction,
                        text_content=message.text_content,
                        file_content=message.file_content,
                        file_name=message.file_name,
                    )

                    ##################
                    # STORE LISTENER #
                    ##################
                    await listener(cursor, message)

                    await cursor.execute("""
                        UPDATE messages
                        SET processed_at = now()
                        WHERE id = %s
                    """, (message.id,))


    def _log_store_access(
        self,
        method, role, gateway, direction,
        text_content, file_content, file_name,
    ):
        text = f"Text: {text_content or "None"}"
        file = f"Filename: {file_name or file_content or "None"}"

        self.logger.info(
            "%-8s %-10s %-10s %-10s %-50s %-50s",
            method[:8], role[:10], gateway[:10], direction[:10],
            truncate(text, max_length=50, flat=True),
            truncate(file, max_length=50, flat=True)
        )


    # Token optimizations:
    #   1. Limit messages to the last N hours
    #   2. Use only the latest uploaded CV
    async def load_unresolved_messages(self, cursor, *, chat_id) -> list[MessageEntity]:
        await cursor.execute("""
            SELECT
                id,
                role,
                gateway,
                direction,
                text_content,
                file_content,
                file_name,
                external_chat_id,
                external_user_id,
                external_user_name,
                external_message_id,
                attributes,
                created_at,
                processed_at,
                resolved_at
            FROM messages
            WHERE resolved_at IS NULL AND external_chat_id = %s
            ORDER BY id
        """, (chat_id,))

        rows = await cursor.fetchall()

        return [row_to_message(row) for row in rows]


    async def sync_store_with_gateway(
        self,
        cursor,
        *,
        message_id,
        external_chat_id=None,
        external_user_id=None,
        external_user_name=None,
        external_message_id=None
    ):
        await cursor.execute("""
            UPDATE messages
            SET
                external_chat_id = %s,
                external_user_id = %s,
                external_user_name = %s,
                external_message_id = %s
            WHERE id = %s
        """, (
            external_chat_id,
            external_user_id,
            external_user_name,
            external_message_id,
            message_id,
        ))


    # only conn_silent user
    async def resolve_session(self, external_chat_id):
        async with self._with_transaction(conn=self.conn_silent) as cursor:
            await cursor.execute("""
                UPDATE messages
                SET resolved_at = now()
                WHERE resolved_at IS NULL AND external_chat_id = %s
            """, (external_chat_id,))


    # another table
    async def store_document(self, cursor, *, search_initiator, document):
        await cursor.execute("""
            INSERT INTO documents (
                source,
                provider,
                document,
                embedding,
                search_initiator
            ) VALUES (%s, %s, %s, %s, %s)
        """, (
            "linkedin",
            "brightdata",
            Jsonb(document),
            None, # Report does it
            search_initiator,
        ))

    async def load_search_results(
        self,
        cursor,
        *,
        search_initiator
    ) -> list[DocumentEntity]:

        await cursor.execute("""
            SELECT
                id,
                source,
                provider,
                document,
                embedding,
                search_initiator,
                created_at
            FROM documents
            WHERE search_initiator = %s
        """, (search_initiator,))

        rows = await cursor.fetchall()

        return [row_to_document(row) for row in rows]
