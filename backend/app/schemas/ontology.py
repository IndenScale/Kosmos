import uuid
from pydantic import BaseModel, field_validator
from typing import Optional, List

class OntologyNodeRead(BaseModel):
    """A schema for reading ontology node data."""
    id: uuid.UUID
    name: str
    
    @field_validator('id', mode='before', check_fields=False)
    @classmethod
    def uuid_from_bytes(cls, v):
        if isinstance(v, bytes):
            return uuid.UUID(bytes=v)
        return v

    class Config:
        from_attributes = True
