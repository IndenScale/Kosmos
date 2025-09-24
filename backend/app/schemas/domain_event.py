import uuid
import json
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, Optional

from ..models.domain_events import EventStatus

class DomainEventRead(BaseModel):
    """
    Pydantic schema for reading a domain event.
    """
    id: uuid.UUID
    correlation_id: Optional[uuid.UUID]
    aggregate_id: str
    event_type: str
    payload: Dict[str, Any]
    status: EventStatus
    created_at: datetime
    processed_at: Optional[datetime]
    error_message: Optional[str]

    @field_validator('payload', mode='before')
    @classmethod
    def payload_to_dict(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                raise ValueError('payload is not a valid JSON string')
        return v

    class Config:
        from_attributes = True
