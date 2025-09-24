"""
Pydantic schemas for Assessment Jobs, Findings, and Evidence.
"""
from pydantic import BaseModel
from typing import List, Optional
from enum import Enum
from uuid import UUID

from .framework_schemas import ControlItemDefinitionResponse

# --- Enums ---

class JudgementEnum(str, Enum):
    """
    Defines the allowed values for an assessment judgement.
    Inherits from `str` to be easily JSON-serializable.
    """
    CONFORMANT = "符合"
    NON_CONFORMANT = "不符合"
    PARTIALLY_CONFORMANT = "部分符合"
    NOT_APPLICABLE = "不涉及"
    UNCONFIRMED = "无法确认"

# --- Knowledge Space Link Schemas ---

class KnowledgeSpaceLink(BaseModel):
    ks_id: str # This is a UUID but comes from the core service as a string
    role: str # 'target' or 'reference'

# --- Evidence Schemas ---

class EvidenceBase(BaseModel):
    doc_id: str
    start_line: int
    end_line: int

class EvidenceCreate(EvidenceBase):
    pass

class EvidenceResponse(EvidenceBase):
    id: UUID
    finding_id: UUID

    class Config:
        from_attributes = True

# --- Assessment Finding Schemas ---

class AssessmentFindingBase(BaseModel):
    judgement: Optional[JudgementEnum] = None
    comment: Optional[str] = None
    supplement: Optional[str] = None

class AssessmentFindingUpdate(AssessmentFindingBase):
    pass

class AssessmentFindingResponse(AssessmentFindingBase):
    id: UUID
    job_id: UUID
    control_item_def_id: UUID
    evidences: List[EvidenceResponse] = []
    control_item_definition: ControlItemDefinitionResponse # Include the definition details

    class Config:
        from_attributes = True

# --- Assessment Job Schemas ---

class JobBase(BaseModel):
    name: Optional[str] = None
    framework_id: UUID

class JobCreate(JobBase):
    knowledge_spaces: List[KnowledgeSpaceLink]


class JobCreateResponse(JobBase):
    id: UUID
    status: str
    findings_created: int

    class Config:
        from_attributes = True


class JobsDeleteRequest(BaseModel):
    job_ids: List[UUID]


class JobSummaryResponse(JobBase):
    id: UUID
    status: str
    findings_summary: dict = {}
    knowledge_spaces: List[KnowledgeSpaceLink] = []

    class Config:
        from_attributes = True


class JobResponse(JobBase):
    id: UUID
    status: str
    findings: List[AssessmentFindingResponse] = []
    # We might want a way to see the linked KSs here too
    
    class Config:
        from_attributes = True
