from datetime import datetime
from dataclasses import dataclass

@dataclass
class UserEntity:
    id: int
    gateway: str
    external_chat_id: str
    external_user_id: str
    external_user_name: str
    created_at: datetime


def row_to_user(row):
    return UserEntity(
        id=row[0],
        gateway=row[1],
        external_chat_id=row[2],
        external_user_id=row[3],
        external_user_name=row[4],
        created_at=row[5],
    )
