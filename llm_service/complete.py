import json
import asyncio
import logging

from openai import OpenAI, OpenAIError

from psycopg import AsyncCursor

from store.entities.message_entity import MessageEntity
from store.messages_store import MessagesStore


class LLMCompletionService:
    """
    The LLM service seen as a plain function: it takes a prompt from another
    service and hands the answer back, without touching the chat history.

    A request is a message on the `llm` channel carrying:

        attributes = {
            "llm_request": {
                "instructions": str,        # developer message
                "input": <json>,            # user message, serialized as JSON
                "schema": <json schema>,    # optional, for a structured answer
                "schema_name": str,         # optional, names that schema
            },
            "llm_reply": {
                "direction": str,           # channel the answer goes back to
                "role": str,                # role the answer is stored under
                "context": <json>,          # echoed back untouched
            },
        }

    The answer is a message on `llm_reply.direction` carrying:

        attributes = {
            "llm_reply": <the request's llm_reply, unchanged>,
            "llm_output": <parsed JSON, or plain text when no schema>,
            "llm_error": str | None,
            "llm_model": str,
            "llm_usage": {...},
        }

    An answer is always sent, errors included, so the caller is never left
    waiting on a reply that will not come.
    """

    def __init__(self, openai_token: str, openai_model: str, messages_store: MessagesStore):
        self.logger = logging.getLogger("llm_completion")
        self.logger.setLevel(logging.INFO)

        self.openai_client = OpenAI(api_key=openai_token)
        self.openai_model = openai_model

        self.messages_store = messages_store


    async def run(self):
        await self.messages_store.listen(
            gateway="telegram",
            direction="llm",
            listener=self.complete
        )


    ##################
    # STORE LISTENER #
    ##################

    async def complete(self, cursor: AsyncCursor, message: MessageEntity):

        attributes = message.attributes or {}

        request = attributes.get("llm_request") or {}
        reply = attributes.get("llm_reply") or {}

        direction = reply.get("direction")

        if not direction:
            self.logger.error("[COMPLETE][ERROR] No reply direction, dropping request")
            return

        output, error, usage = await asyncio.to_thread(self._ask_openai, request)

        if error is not None:
            self.logger.error("[COMPLETE][ERROR] %s", error)

        await self.messages_store.store(
            role=reply.get("role") or "llm",
            gateway=message.gateway,
            direction=direction,
            external_chat_id=message.external_chat_id,
            external_user_id=message.external_user_id,
            external_user_name=message.external_user_name,
            attributes={
                "llm_reply": reply,
                "llm_output": output,
                "llm_error": error,
                "llm_model": self.openai_model,
                "llm_usage": usage,
            },
        )


    def _ask_openai(self, request: dict) -> tuple[object, str | None, dict | None]:
        """
        Run one request against OpenAI. Returns (output, error, usage), where
        exactly one of output and error is set.
        """

        schema = request.get("schema")

        payload = {
            "model": self.openai_model,
            "input": [
                {
                    "role": "developer",
                    "content": request.get("instructions") or "",
                },
                {
                    "role": "user",
                    "content": self._as_text(request.get("input")),
                },
            ],
        }

        if schema is not None:
            payload["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": request.get("schema_name") or "response",
                    "strict": True,
                    "schema": schema,
                }
            }

        try:
            response = self.openai_client.responses.create(**payload)

            output = (
                json.loads(response.output_text)
                if schema is not None
                else response.output_text
            )

            return output, None, response.usage.model_dump()

        except (OpenAIError, json.JSONDecodeError, TypeError, ValueError) as error:
            return None, f"{type(error).__name__}: {error}", None


    def _as_text(self, value) -> str:
        if isinstance(value, str):
            return value

        return json.dumps(value, ensure_ascii=False)
