"""
Pydantic schemas for Assessment Sessions.
"""
from pydantic import BaseModel, Field, computed_field
from typing import List, Optional
from uuid import UUID
import datetime

from .job_schemas import AssessmentFindingResponse

class SessionBase(BaseModel):
    pass

class SessionCreate(BaseModel):
    # Defines how many pending findings to include in the new session.
    batch_size: int = 5

class SessionUpdate(BaseModel):
    action_limit: Optional[int] = Field(None, description="Set a new action limit for the session.")
    error_limit: Optional[int] = Field(None, description="Set a new error limit for the session.")
    warning_limit: Optional[int] = Field(None, description="Set a new warning limit for the session.")
    timeout_seconds: Optional[int] = Field(None, description="Set a new timeout in seconds for the session.")

class SessionRejectRequest(BaseModel):
    reason: str

class SessionFailRequest(BaseModel):
    reason: str

class SessionSummaryResponse(SessionBase):
    """A more lightweight session response for list views."""
    id: UUID
    job_id: UUID
    status: str
    created_at: datetime.datetime
    action_count: int
    action_limit: int
    
    # This field is populated from the relationship, but not included in the final JSON
    findings: List[AssessmentFindingResponse] = Field(exclude=True)

    @computed_field
    @property
    def findings_count(self) -> int:
        return len(self.findings)

    class Config:
        from_attributes = True

class SessionResponse(SessionBase):
    id: UUID
    job_id: UUID
    status: str
    log_file_url: Optional[str] = None
    
    action_count: int
    action_limit: int
    error_count: int
    error_limit: int
    warning_count: int
    warning_limit: int
    created_at: datetime.datetime
    timeout_seconds: int

    # The list of findings that are the "contract" for this session
    findings: List[AssessmentFindingResponse] = []

    class Config:
        from_attributes = True
