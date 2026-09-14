from datetime import datetime
from dataclasses import dataclass, field

@dataclass
class MessageEntity:
    id: int
    role: str
    gateway: str
    direction: str

    text_content: str | None
    reply_markup: list[str] | None
    file_content: str | None
    file_name: str | None

    external_chat_id: str | None
    external_user_id: str | None
    external_user_name: str | None
    external_message_id: str | None

    llm_response: dict | None
    attributes: dict | None

    created_at: datetime
    processed_at: datetime | None
    resolved_at: datetime | None


def row_to_message(row):
    return MessageEntity(
        id=row[0],
        role=row[1],
        gateway=row[2],
        direction=row[3],
        text_content=row[4],
        reply_markup=row[5],
        file_content=row[6],
        file_name=row[7],
        external_chat_id=row[8],
        external_user_id=row[9],
        external_user_name=row[10],
        external_message_id=row[11],
        llm_response=row[12],
        attributes=row[13],
        created_at=row[14],
        processed_at=row[15],
        resolved_at=row[16]
    )
