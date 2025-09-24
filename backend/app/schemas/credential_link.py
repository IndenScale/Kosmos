"""
Pydantic schemas for the KnowledgeSpace-Credential link.
"""
import uuid
from pydantic import BaseModel, Field, field_validator
from .credential import ModelCredentialRead

# --- Base Schemas ---

class CredentialLinkBase(BaseModel):
    """Base model for link properties."""
    priority_level: int = Field(0, description="优先级，数字越大，优先级越高。")
    weight: int = Field(1, ge=1, description="权重，在同一优先级内，权重越高被选中的概率越大。")

# --- Schemas for API Operations ---

class CredentialLinkCreate(CredentialLinkBase):
    """Schema for linking a credential to a knowledge space."""
    credential_id: uuid.UUID = Field(..., description="要链接的模型凭证的ID。")

class CredentialLinkUpdate(CredentialLinkBase):
    """Schema for updating an existing credential link."""
    pass

class CredentialLinkRead(CredentialLinkBase):
    """Schema for reading a credential link, including details of the credential."""
    knowledge_space_id: uuid.UUID
    credential: ModelCredentialRead

    class Config:
        from_attributes = True
