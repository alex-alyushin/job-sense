import logging

from psycopg import sql
from contextlib import asynccontextmanager

from store.message_entity import MessageEntity, row_to_message
from store.db_utils import database_connect_async

from common.utils import truncate

class MessagesStore:

    def __init__(self):
        self.conn_notify = None
        self.conn_listen = None
        self.conn_silent = None

        # это должно быть глобально - например в main
        logging.basicConfig(
            level=logging.WARNING,
            format="%(asctime)s [%(levelname)s] %(message)s"
        )

        # а это окей
        self.logger = logging.getLogger("store")
        self.logger.setLevel(logging.INFO)


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


    def _log_store_access(
        self,
        method, role, gateway, direction,
        text_content, file_content
    ):
        text_content = f"Text: {"None" if text_content is None else text_content}"
        file_content = f"File: {"None" if file_content is None else file_content}"

        self.logger.info(
            "%-8s %-12s %-12s %-12s %-60s %-60s",
            method[:8], role[:12], gateway[:12], direction[:12],
            truncate(text_content, max_length=60, flat=True),
            truncate(file_content, max_length=60, flat=True)
        )


    @classmethod
    async def create(cls, *, host, dbname, user, password):
        ctx = cls()

        ctx.conn_notify = await database_connect_async(
            host=host, dbname=dbname, user=user, password=password
        )

        ctx.conn_listen = await database_connect_async(
            host=host, dbname=dbname, user=user, password=password
        )

        ctx.conn_silent = await database_connect_async(
            host=host, dbname=dbname, user=user, password=password
        )

        return ctx


    async def store(
        self, role, gateway, direction,
        text_content=None, file_content=None,
        external_chat_id=None, external_user_id=None,
        external_user_name=None, external_message_id=None
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
                    external_chat_id,
                    external_user_id,
                    external_user_name,
                    external_message_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                role,
                gateway,
                direction,
                text_content,
                file_content,
                external_chat_id,
                external_user_id,
                external_user_name,
                external_message_id,
            ))

            # debug info
            self._log_store_access(
                "Store",
                role=role,
                gateway=gateway,
                direction=direction,
                text_content=text_content,
                file_content=file_content
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
                            external_chat_id,
                            external_user_id,
                            external_user_name,
                            external_message_id,
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

                    # debug info
                    self._log_store_access(
                        "Load",
                        role=message.role,
                        gateway=message.gateway,
                        direction=direction,
                        text_content=message.text_content,
                        file_content=message.file_content
                    )

                    await listener(message)

                    await cursor.execute("""
                        UPDATE messages
                        SET processed_at = now()
                        WHERE id = %s
                    """, (message.id,))


    async def load_unresolved_messages(self, chat_id) -> list[MessageEntity]:

        async with self._with_transaction(conn=self.conn_silent) as cursor:
            await cursor.execute("""
                SELECT
                    id,
                    role,
                    gateway,
                    direction,
                    text_content,
                    file_content,
                    external_chat_id,
                    external_user_id,
                    external_user_name,
                    external_message_id,
                    created_at,
                    processed_at,
                    resolved_at
                FROM messages
                WHERE resolved_at IS NULL AND external_chat_id = %s
                ORDER BY id
            """, (chat_id,))

            rows = await cursor.fetchall()

            messages = [row_to_message(row) for row in rows]

        return messages


    # это еще не тестировалось!
    async def sync_store_with_gateway(
        self, message_id,
        external_chat_id=None,
        external_user_id=None,
        external_user_name=None,
        external_message_id=None
    ) -> None:

        async with self._with_transaction(conn=self.conn_silent) as cursor:
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

