"""
Pydantic schemas for Chunk models.
"""
import uuid
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from .pagination import PaginatedResponse
from .ontology import OntologyNodeRead

class ChunkRead(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    parent_id: Optional[uuid.UUID] = None
    type: str
    level: int
    start_line: int
    end_line: int
    char_count: int
    raw_content: Optional[str] = None
    summary: Optional[str] = None
    paraphrase: Optional[str] = None
    indexing_status: str
    ontology_tags: List[OntologyNodeRead] = Field(default_factory=list)

    @field_validator(
        'id', 'document_id', 'parent_id',
        mode='before', check_fields=False
    )
    @classmethod
    def uuid_from_bytes(cls, v):
        if isinstance(v, bytes):
            return uuid.UUID(bytes=v)
        return v

    class Config:
        from_attributes = True

class PaginatedChunkResponse(PaginatedResponse[ChunkRead]):
    pass
