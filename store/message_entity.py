from datetime import datetime
from dataclasses import dataclass, field

@dataclass
class MessageEntity:
    id: int
    role: str
    gateway: str
    direction: str

    text_content: str | None
    file_content: str | None

    external_chat_id: str | None
    external_user_id: str | None
    external_user_name: str | None
    external_message_id: str | None

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
        file_content=row[5],
        external_chat_id=row[6],
        external_user_id=row[7],
        external_user_name=row[8],
        external_message_id=row[9],
        created_at=row[10],
        processed_at=row[11],
        resolved_at=row[12]
    )
