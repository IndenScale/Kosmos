import uuid
from datetime import datetime
from pydantic import BaseModel, Field, computed_field, field_validator
from typing import Any, Optional

# --- Helper schemas for nested data ---

class OntologyVersionRead(BaseModel):
    """Minimal schema for an ontology version, containing the pre-serialized tree."""
    serialized_nodes: dict[str, Any]

    class Config:
        from_attributes = True

class OntologyRead(BaseModel):
    """Minimal schema for an ontology, containing the active version."""
    active_version: OntologyVersionRead | None

    class Config:
        from_attributes = True

# --- Main schemas ---

class KnowledgeSpaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    ontology_dictionary: dict[str, Any] | None = None

class KnowledgeSpaceUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    ontology_dictionary: dict[str, Any] | None = None

class KnowledgeSpaceBase(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    created_at: datetime

    class Config:
        from_attributes = True

class KnowledgeSpaceRead(KnowledgeSpaceBase):
    """Schema for detailed view, including the simplified ontology dictionary."""
    ontology_dictionary: dict[str, Any] = Field(default_factory=dict)

class KnowledgeSpaceListItem(KnowledgeSpaceBase):
    """Schema for list view, including a simplified, name-only ontology dict."""
    ontology_simple_dict: dict[str, Any] = Field(default_factory=dict)

# --- AI Configuration Schemas ---

class AIConfigEmbedding(BaseModel):
    provider: Optional[str] = Field(None, description="e.g., 'dashscope', 'openai'")
    model_name: Optional[str] = Field(None, description="e.g., 'text-embedding-v2'")
    dimension: Optional[int] = Field(None, description="The dimension of the embedding vector.")

class AIConfigTaskModel(BaseModel):
    """A generic model for task-specific configurations like chunking, tagging, etc."""
    provider: Optional[str] = Field(None, description="e.g., 'dashscope', 'openai'")
    model_name: Optional[str] = Field(None, description="e.g., 'qwen-max'")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Sampling temperature.")

class AIConfigVLM(BaseModel):
    provider: Optional[str] = Field(None, description="e.g., 'dashscope', 'openai'")
    model_name: Optional[str] = Field(None, description="e.g., 'qwen-vl-max'")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Sampling temperature.")

class AIConfigurationRead(BaseModel):
    """Schema for reading the full AI configuration of a knowledge space."""
    embedding: AIConfigEmbedding
    chunking: AIConfigTaskModel
    tagging: AIConfigTaskModel
    asset_analysis: AIConfigVLM

class AIConfigurationUpdate(BaseModel):
    """
    Schema for partially updating the AI configuration.
    Only the provided fields will be updated.
    """
    embedding: Optional[AIConfigEmbedding] = None
    chunking: Optional[AIConfigTaskModel] = None
    tagging: Optional[AIConfigTaskModel] = None
    asset_analysis: Optional[AIConfigVLM] = None
