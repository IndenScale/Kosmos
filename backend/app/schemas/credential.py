import uuid
from pydantic import BaseModel, Field, field_validator
from ..models.credential import CredentialType, ModelFamily

# --- ModelCredential Schemas ---

class ModelCredentialBase(BaseModel):
    credential_type: CredentialType
    model_family: ModelFamily
    provider: str = Field(..., description="The service provider, e.g., 'openai', 'deepseek', or an internal service name.")
    model_name: str
    base_url: str | None = None
    is_default: bool = False

    @field_validator('credential_type', 'model_family', mode='before')
    @classmethod
    def lowercase_enums(cls, v):
        """Allow uppercase enum values by converting them to lowercase before validation."""
        if isinstance(v, str):
            return v.lower()
        return v

class ModelCredentialCreate(ModelCredentialBase):
    # The API key is now optional
    api_key: str | None = Field(None, description="API key, if required by the provider.")

class ModelCredentialRead(ModelCredentialBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    # For security, we never expose the key. We provide a masked version or indicate its absence.
    masked_api_key: str

    class Config:
        from_attributes = True

# --- KnowledgeSpace <-> Credential Link Schemas ---

class CredentialLinkCreate(BaseModel):
    credential_id: uuid.UUID
    priority_level: int = Field(0, ge=0, description="Higher number means higher priority.")
    weight: int = Field(1, ge=1, description="Weight for load balancing within the same priority level.")

from typing import Optional

class ModelCredentialUpdate(BaseModel):
    model_family: Optional[ModelFamily] = None
    provider: Optional[str] = Field(None, description="The service provider, e.g., 'openai', 'deepseek'.")
    model_name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = Field(None, description="A new plain text API key. Will be encrypted before storage.")
    is_default: Optional[bool] = None
