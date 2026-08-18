from datetime import datetime
from dataclasses import dataclass

@dataclass
class UserCVEntity:
    id: int
    content: str
    embedding: list[float] | None
    user_id: int
    created_at: datetime


def row_to_cv(row):
    return UserCVEntity(
        id=row[0],
        content=row[1],
        embedding=row[2],
        user_id=row[3],
        created_at=row[4],
    )
