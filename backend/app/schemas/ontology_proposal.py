import uuid
from datetime import datetime
from pydantic import BaseModel, field_validator
from typing import Optional

from ..models.ontology_change_proposal import ProposalType, ProposalStatus

class OntologyChangeProposalBase(BaseModel):
    proposal_type: ProposalType
    proposal_details: dict
    source_mode: str

class OntologyChangeProposalRead(OntologyChangeProposalBase):
    id: uuid.UUID
    knowledge_space_id: uuid.UUID
    source_job_id: uuid.UUID
    source_chunk_id: uuid.UUID
    status: ProposalStatus
    created_at: datetime
    reviewed_by_user_id: Optional[uuid.UUID] = None
    reviewed_at: Optional[datetime] = None

    @field_validator(
        'id', 'knowledge_space_id', 'source_job_id', 'source_chunk_id', 'reviewed_by_user_id',
        mode='before', check_fields=False
    )
    @classmethod
    def uuid_from_bytes(cls, v):
        if isinstance(v, bytes):
            return uuid.UUID(bytes=v)
        return v

    class Config:
        from_attributes = True
