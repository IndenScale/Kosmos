import uuid
import enum
from sqlalchemy import Column, String, Boolean, Enum as SQLAlchemyEnum, ForeignKey
from sqlalchemy.orm import relationship
from ..models.base import Base, UUIDChar

class CredentialType(str, enum.Enum):
    VLM = "vlm"
    LLM = "llm"
    EMBEDDING = "embedding"
    SLM = "slm"
    IMAGE_GEN = "image_gen"
    OMNI = "omni"
    NONE = "none"

class ModelFamily(str, enum.Enum):
    OPENAI = "openai"
    GEMINI = "gemini"
    ANTHROPIC = "anthropic"

class ModelCredential(Base):
    __tablename__ = "model_credentials"

    id = Column(UUIDChar, primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUIDChar, ForeignKey("users.id"), nullable=False, index=True)
    
    credential_type = Column(SQLAlchemyEnum(CredentialType), nullable=False, index=True)
    model_family = Column(SQLAlchemyEnum(ModelFamily), nullable=False)
    
    # Provider is now a flexible string to accommodate custom/internal endpoints
    provider = Column(String, nullable=False)
    
    model_name = Column(String, nullable=False)
    
    # User can override this for private endpoints
    base_url = Column(String, nullable=True) 
    
    # API key is now optional for local models or services without auth
    encrypted_api_key = Column(String, nullable=True)
    
    is_default = Column(Boolean, default=False, nullable=False)

    # --- Relationships ---
    owner = relationship("User", back_populates="credentials")
    
    # One-to-many relationship to the link table
    knowledge_space_links = relationship("KnowledgeSpaceModelCredentialLink", back_populates="credential", cascade="all, delete-orphan")
