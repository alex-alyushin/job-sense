import logging

import numpy as np

from psycopg import sql
from psycopg.types.json import Jsonb

from contextlib import asynccontextmanager

from store.entities.document_entity import DocumentEntity, row_to_document
from store.entities.message_entity import MessageEntity, row_to_message
from store.entities.user_cv_entity import UserCVEntity, row_to_cv
from store.entities.user_entity import UserEntity, row_to_user

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
        llm_response=None, attributes=None,
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
                    llm_response,
                    attributes
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                Jsonb(llm_response) if llm_response is not None else None,
                Jsonb(attributes) if attributes is not None else None,
            ))

            self._log_store_access(
                "Save",
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
                            llm_response,
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
                        "Read",
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


    async def load_latest_messages(self, cursor, *, chat_id) -> list[MessageEntity]:
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
                llm_response,
                attributes,
                created_at,
                processed_at,
                resolved_at
            FROM messages
            WHERE external_chat_id = %s
                AND role in ('user', 'assistant')
                AND resolved_at IS NULL
            ORDER BY id DESC
            LIMIT 21
        """, (chat_id,))

        rows = await cursor.fetchall()

        return [row_to_message(row) for row in reversed(rows)]
 

    async def update_externals(
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


    async def resolve_session(self, external_chat_id):
        async with self._with_transaction(conn=self.conn_silent) as cursor:
            await cursor.execute("""
                UPDATE messages
                SET resolved_at = now()
                WHERE resolved_at IS NULL AND external_chat_id = %s
            """, (external_chat_id,))


    def _log_store_access(
        self,
        method, role, gateway, direction,
        text_content, file_content, file_name,
    ):
        text = text_content or "no_text"
        file = file_name or file_content or "no_file"

        self.logger.info(
            "%-6s %-16s from:%-16s to:%-16s Text: %-48s File: %-48s",
            method[:4], gateway[:16],
            role[:16], direction[:16],
            truncate(text, max_length=48, flat=True),
            truncate(file, max_length=48, flat=True)
        )


    #########
    # USERS #
    #########

    async def ensure_user(
        self, cursor, *,
        message: MessageEntity,
    ):
        await cursor.execute("""
            SELECT
                id,
                gateway,
                external_chat_id,
                external_user_id,
                external_user_name,
                created_at
            FROM users
            WHERE gateway = %s
                AND external_chat_id = %s
                AND external_user_id = %s
        """, (
            message.gateway,
            message.external_chat_id,
            message.external_user_id,
        ))

        row = await cursor.fetchone()

        if row is not None:
            return row_to_user(row)

        await cursor.execute("""
            INSERT INTO users (
                gateway,
                external_chat_id,
                external_user_id,
                external_user_name
            ) VALUES (%s, %s, %s, %s)
            ON CONFLICT (gateway, external_chat_id, external_user_id)
            DO UPDATE SET external_user_name = EXCLUDED.external_user_name
            RETURNING
                id,
                gateway,
                external_chat_id,
                external_user_id,
                external_user_name,
                created_at
        """, (
            message.gateway,
            message.external_chat_id,
            message.external_user_id,
            message.external_user_name,
        ))

        row = await cursor.fetchone()

        if row is not None:
            return row_to_user(row)

        return None


    ############
    # USER CVs #
    ############

    async def store_user_cv(
        self, cursor, *,
        content: str,
        embedding: np.ndarray,
        user: UserEntity,
    ) -> UserCVEntity | None:
        await cursor.execute("""
            INSERT INTO user_cvs (
                content,
                embedding,
                user_id
            ) VALUES (%s, %s, %s)
            RETURNING
                id,
                content,
                embedding,
                user_id,
                created_at
        """, (
            content,
            embedding,
            user.id,
        ))

        row = await cursor.fetchone()

        if row is not None:
            return row_to_cv(row)

        return None


    #############
    # DOCUMENTS #
    #############

    async def store_document(
        self, cursor, *,
        document: dict,
        embedding: np.ndarray,
        call_id: str,
        user_id: int,
    ):
        await cursor.execute("""
            INSERT INTO documents (
                source,
                provider,
                document,
                embedding,
                call_id,
                user_id
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            "linkedin",
            "brightdata",
            Jsonb(document),
            embedding,
            call_id,
            user_id,
        ))


    async def load_documents(
        self, cursor, *,
        call_id: str,
    ) -> list[tuple[DocumentEntity, float]]:

        await cursor.execute("""
            SELECT
                documents.id,
                documents.source,
                documents.provider,
                documents.document,
                documents.embedding,
                documents.call_id,
                documents.user_id,
                documents.created_at,
                1 - (documents.embedding <=> user_cvs.embedding) AS cv_similarity
            FROM documents
            LEFT JOIN LATERAL (
                SELECT embedding
                FROM user_cvs
                WHERE user_cvs.user_id = documents.user_id
                ORDER BY user_cvs.id DESC
                LIMIT 1
            ) AS user_cvs ON TRUE
            WHERE documents.call_id = %s
            ORDER BY cv_similarity
        """, (call_id,))

        rows = await cursor.fetchall()

        return [(
            row_to_document(row[:8]),
            row[8], # cv similarity
        ) for row in rows]
