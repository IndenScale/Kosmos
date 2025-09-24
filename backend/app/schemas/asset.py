import uuid
from datetime import datetime
from typing import List, Optional, Generic, TypeVar
from pydantic import BaseModel, Field, field_validator

from ..models.asset import AssetAnalysisStatus, AssetType

# Generic TypeVar for paginated responses
T = TypeVar('T')

# --- Base Schemas ---

class AssetBase(BaseModel):
    asset_type: AssetType
    file_type: str
    analysis_status: AssetAnalysisStatus

class AssetRead(AssetBase):
    id: uuid.UUID
    knowledge_space_id: uuid.UUID
    # An asset might not be directly tied to a single document (e.g., future use cases)
    document_id: Optional[uuid.UUID] = None
    storage_path: str
    created_at: datetime
    updated_at: datetime

    @field_validator(
        'id', 'knowledge_space_id', 'document_id',
        mode='before', check_fields=False
    )
    @classmethod
    def uuid_from_bytes(cls, v):
        if isinstance(v, bytes):
            return uuid.UUID(bytes=v)
        return v

    class Config:
        from_attributes = True

class AssetWithAnalysis(AssetRead):
    """Asset schema including its analysis result."""
    analysis_result: Optional[str] = None
    model_version: Optional[str] = None

# --- API Schemas ---

class AssetFilterParams(BaseModel):
    """Query parameters for filtering assets, injected via Depends()."""
    knowledge_space_id: Optional[uuid.UUID] = Field(None, description="Optionally filter assets by a specific knowledge space ID.")
    document_id: Optional[uuid.UUID] = Field(None, description="Filter assets by a specific document ID.")
    asset_type: Optional[AssetType] = Field(None, description="Filter by asset type (e.g., 'figure', 'table').")
    analysis_status: Optional[AssetAnalysisStatus] = Field(None, description="Filter by analysis status.")
    # Using Query for list parameters
    file_types: Optional[List[str]] = Field(None, description="Filter by a list of file types (e.g., 'image/png', 'image/jpeg').")
    limit: int = Field(20, ge=1, le=100, description="The maximum number of assets to return.")
    cursor: Optional[str] = Field(None, description="The cursor for pagination, based on the asset's creation timestamp.")

    @field_validator(
        'knowledge_space_id', 'document_id',
        mode='before', check_fields=False
    )
    @classmethod
    def uuid_from_bytes(cls, v):
        if isinstance(v, bytes):
            return uuid.UUID(bytes=v)
        return v

class PaginatedAssetResponse(BaseModel, Generic[T]):
    """Generic paginated response schema."""
    items: List[T]
    total_count: int
    next_cursor: Optional[str] = None

class AssetBulkRequest(BaseModel):
    """Base model for bulk operations on assets."""
    asset_ids: List[uuid.UUID] = Field(..., min_items=1, description="A list of asset IDs for the bulk operation.")
    knowledge_space_id: uuid.UUID = Field(..., description="The knowledge space ID to which all assets must belong.")

    @field_validator(
        'asset_ids', 'knowledge_space_id',
        mode='before', check_fields=False
    )
    @classmethod
    def uuid_from_bytes(cls, v):
        if isinstance(v, bytes):
            return uuid.UUID(bytes=v)
        if isinstance(v, list):
            return [uuid.UUID(bytes=i) if isinstance(i, bytes) else i for i in v]
        return v

class AssetBulkDeleteResponse(BaseModel):
    deleted_count: int

class AssetBulkGetResponse(BaseModel):
    assets: List[AssetWithAnalysis]

class AssetAnalysisResponse(BaseModel):
    """Schema for returning the result of a VLM analysis on an asset."""
    analysis_status: AssetAnalysisStatus
    description: Optional[str] = None
    model_version: Optional[str] = None
    detail: str
