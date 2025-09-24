import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, text
from sqlalchemy.orm import relationship, Mapped, mapped_column
from ..models.base import Base, UUIDChar
from ..core.config import settings
import json

class KnowledgeSpace(Base):
    __tablename__ = "knowledge_spaces"

    id = Column(UUIDChar, primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUIDChar, ForeignKey("users.id"), nullable=False) # Foreign key to User
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    ai_configuration: Mapped[dict] = mapped_column(
        JSON, 
        nullable=False, 
        default=lambda: settings.DEFAULT_AI_CONFIGURATION
    )

    @property
    def knowledge_space_id(self):
        return self.id

    # Relationships
    owner = relationship("User")
    members = relationship("KnowledgeSpaceMember", back_populates="knowledge_space", cascade="all, delete-orphan")
    
    # One-to-many relationship to the link table
    credential_links = relationship("KnowledgeSpaceModelCredentialLink", back_populates="knowledge_space", cascade="all, delete-orphan")
    
    # One-to-one relationship to the Ontology repository
    ontology = relationship("Ontology", uselist=False, back_populates="knowledge_space", cascade="all, delete-orphan")
    
    # One-to-many relationship to Documents
    documents = relationship("Document", back_populates="knowledge_space", cascade="all, delete-orphan")
    
    # One-to-many relationship to Jobs
    jobs = relationship("Job", back_populates="knowledge_space", cascade="all, delete-orphan")
