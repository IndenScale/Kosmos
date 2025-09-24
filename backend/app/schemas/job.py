import uuid
import enum
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any

from fastapi import Query, Depends

from ..models.credential import CredentialType
from ..models.job import JobStatus, JobType

# --- Enums ---

class TaggingMode(str, enum.Enum):
    ASSIGNMENT = "assignment"
    EVOLUTION = "evolution"
    SHADOW = "shadow"

# --- API Input Schemas ---

class JobCreate(BaseModel):
    """Schema for creating a new job."""
    document_id: uuid.UUID = Field(..., description="The document to run the job on.")
    job_type: JobType = Field(
        ...,
        description="The type of job to create. Supported types: 'document_processing', 'chunking', 'tagging', 'indexing', 'asset_analysis'."
    )
    force: bool = Field(
        False,
        description="If true, any existing 'pending' or 'running' job of the same type for the document will be aborted before creating the new one."
    )
    context: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "A dictionary for job-specific parameters. "
            "Examples: "
            "For 'tagging', provide {'mode': 'assignment' | 'evolution' | 'shadow'}. "
            "For 'chunking', provide {'credential_type_preference': 'SLM' | 'LLM'}. "
            "For 'document_processing', provide {'extract_embedded_documents': false} to skip processing embedded files. "
            "'asset_analysis' does not require a context."
        )
    )

class JobBatchCreateRequest(BaseModel):
    """Schema for creating a batch of jobs."""
    document_ids: List[uuid.UUID] = Field(..., min_items=1, description="A list of document IDs to run jobs on.")
    job_type: JobType = Field(
        ...,
        description="The type of job to create for all documents. Supported types: 'document_processing', 'chunking', 'tagging', 'indexing', 'asset_analysis'."
    )
    force: bool = Field(
        False,
        description="If true, any existing 'pending' or 'running' jobs of the same type for the documents will be aborted before creating new ones."
    )
    context: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "A dictionary for job-specific parameters, applied to all jobs in the batch. "
            "Examples: "
            "For 'tagging', provide {'mode': 'assignment' | 'evolution' | 'shadow'}. "
            "For 'chunking', provide {'credential_type_preference': 'SLM' | 'LLM'}. "
            "For 'document_processing', provide {'extract_embedded_documents': false} to skip processing embedded files. "
            "'asset_analysis' does not require a context."
        )
    )

class JobFilterParams:
    """Dependency to handle job filtering query parameters."""
    def __init__(
        self,
        knowledge_space_id: Optional[uuid.UUID] = Query(None, description="Filter jobs by knowledge space ID."),
        document_id: Optional[uuid.UUID] = Query(None, description="Filter jobs by document ID."),
        job_type: Optional[JobType] = Query(None, description="Filter jobs by type."),
        status: Optional[JobStatus] = Query(None, description="Filter jobs by status."),
        cursor: Optional[str] = Query(None, description="Cursor for pagination."),
        limit: int = Query(20, ge=1, le=100, description="Page size limit."),
    ):
        self.knowledge_space_id = knowledge_space_id
        self.document_id = document_id
        self.job_type = job_type
        self.status = status
        self.cursor = cursor
        self.limit = limit

class JobAbortRequest(BaseModel):
    """Schema for aborting jobs by document IDs."""
    document_ids: List[uuid.UUID] = Field(..., min_items=1, description="A list of document IDs for which to abort jobs.")
    job_type: Optional[JobType] = Field(None, description="Optional: Specify a job type to abort. If omitted, all pending/running jobs for the documents will be aborted.")

class JobBulkDeleteRequest(BaseModel):
    """Schema for bulk deleting jobs by their IDs."""
    job_ids: List[uuid.UUID] = Field(..., min_items=1, description="A list of job IDs to be deleted.")
    force: bool = Field(False, description="If true, delete jobs regardless of their status (e.g., running or pending). Use with caution.")

# --- API Output Schemas ---

class JobAbortResponse(BaseModel):
    """Response for a job abort request."""
    aborted_jobs_count: int


class Job(BaseModel):
    """Detailed job information."""
    id: uuid.UUID
    document_id: Optional[uuid.UUID]
    knowledge_space_id: uuid.UUID
    initiator_id: uuid.UUID
    job_type: JobType
    status: JobStatus
    progress: Optional[dict] = None
    context: Optional[dict] = None
    result: Optional[dict] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class BatchJobCreationResponse(BaseModel):
    """Response for a batch job creation request."""
    submitted_jobs: List[Job]
    failed_documents: Dict[uuid.UUID, str]
