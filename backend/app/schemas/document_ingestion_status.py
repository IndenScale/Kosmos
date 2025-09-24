"""
Pydantic schemas for document ingestion status.
"""
from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID

class DocumentIngestionStatusDetail(BaseModel):
    """Detailed status for a single document."""
    document_id: UUID
    document_name: str
    has_canonical_content: bool
    total_assets: int
    completed_assets: int
    asset_analysis_completion_rate: float
    has_pending_jobs: bool
    suggestions: List[str]

class DocumentIngestionStatusResponse(BaseModel):
    """Overall status response for a knowledge space."""
    knowledge_space_id: UUID
    total_documents: int
    documents_with_canonical_content: int
    documents_with_asset_analysis: int
    documents_with_pending_jobs: int
    canonical_content_rate: float
    asset_analysis_rate: float
    pending_jobs_rate: float
    documents: List[DocumentIngestionStatusDetail]