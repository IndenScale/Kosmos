import uuid
from datetime import datetime
from typing import List, Optional, Dict
from pydantic import BaseModel, Field, field_validator
from ..models.document import DocumentStatus
from ..models.asset import AssetType
from ..models.job import JobType, JobStatus

# =======================================================================
# Reconstructed Schemas
# =======================================================================

class ContentSummary(BaseModel):
    """Provides a summary of the document's canonical content."""
    total_pages: int = Field(..., description="Total number of pages in the document.")
    total_lines: int = Field(..., description="Total number of lines in the canonical content.")
    total_chars: int = Field(..., description="Total number of characters (bytes) in the canonical content file.")

class AssetTypeSummary(BaseModel):
    """Summary for a specific type of asset."""
    total: int = 0
    described: int = 0
    not_described: int = 0

class AssetSummary(BaseModel):
    """Provides a summary of the document's assets."""
    total_assets: int = Field(..., description="Total number of assets linked to the document.")
    by_type: Dict[AssetType, AssetTypeSummary] = Field(..., description="Statistics broken down by asset type.")

class JobStatusSummary(BaseModel):
    """Summary of jobs for a specific type, broken down by status."""
    total: int = 0
    status_counts: Dict[JobStatus, int] = Field(default_factory=dict)

class JobSummary(BaseModel):
    """Provides a summary of jobs related to the document."""
    total_jobs: int = Field(..., description="Total number of jobs associated with the document.")
    by_type: Dict[JobType, JobStatusSummary] = Field(..., description="Statistics broken down by job type.")

class DocumentBase(BaseModel):
    """Base schema with fields common to all document variants."""
    original_filename: str = Field(..., description="The original filename of the document as uploaded.")
    status: DocumentStatus = Field(description="The current processing status of the document.")

class DocumentRead(DocumentBase):
    """Schema for returning full document details to the client."""
    id: uuid.UUID
    knowledge_space_id: uuid.UUID
    uploaded_by: uuid.UUID
    created_at: datetime
    
    content_summary: Optional[ContentSummary] = Field(None, description="Summary of the canonical content, if available.")
    asset_summary: Optional[AssetSummary] = Field(None, description="Summary of the assets, if available.")
    job_summary: Optional[JobSummary] = Field(None, description="Summary of related jobs, if available.")

    class Config:
        from_attributes = True

# =======================================================================
# Document Ingestion Status Schemas
# =======================================================================

class DocumentIngestionStatusDetail(BaseModel):
    """Detailed status for a single document."""
    document_id: uuid.UUID
    document_name: str
    has_canonical_content: bool
    total_assets: int
    completed_assets: int
    asset_analysis_completion_rate: float
    has_pending_jobs: bool
    suggestions: List[str]

class DocumentIngestionStatusResponse(BaseModel):
    """Overall status response for a knowledge space."""
    knowledge_space_id: uuid.UUID
    total_documents: int
    documents_with_canonical_content: int
    documents_with_asset_analysis: int
    documents_with_pending_jobs: int
    canonical_content_rate: float
    asset_analysis_rate: float
    pending_jobs_rate: float
    
    # New, more practical asset analysis metrics
    total_assets_in_ks: int = Field(description="Total number of assets across all valid documents in the knowledge space.")
    total_completed_assets_in_ks: int = Field(description="Total number of assets with completed analysis across all valid documents.")
    overall_asset_analysis_rate: float = Field(description="The true asset analysis completion rate (completed_assets / total_assets)." )

    documents: List[DocumentIngestionStatusDetail]

# =======================================================================
# New Schema for Bulk Delete
# =======================================================================

class DocumentBulkDeleteRequest(BaseModel):
    """Schema for the request body of the bulk document deletion endpoint."""
    document_ids: List[uuid.UUID] = Field(..., min_items=1, description="A list of document IDs to be deleted.")