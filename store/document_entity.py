from datetime import datetime
from dataclasses import dataclass, field

@dataclass
class DocumentEntity:
    id: int
    source: str | None
    provider: str | None
    document: dict | None
    embedding: list[float] | None
    search_initiator: int
    created_at: datetime


def row_to_document(row):
    return DocumentEntity(
        id=row[0],
        source=row[1],
        provider=row[2],
        document=row[3],
        embedding=row[4],
        search_initiator=row[5],
        created_at=row[6],
    )
