import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, UniqueConstraint
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.orm import relationship, backref
from ..models.base import Base, UUIDChar

class DocumentStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PENDING = "pending"
    RUNNING = "running"
    PROCESSED = "processed"
    FAILED = "failed"
    ARCHIVED_AS_DUPLICATE = "archived_as_duplicate"


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUIDChar, primary_key=True, default=uuid.uuid4)
    knowledge_space_id = Column(UUIDChar, ForeignKey("knowledge_spaces.id"), nullable=False)

    # Foreign key to the Original record
    original_id = Column(UUIDChar, ForeignKey("originals.id"), nullable=False)

    # Foreign key to the canonical content for this document
    canonical_content_id = Column(UUIDChar, ForeignKey("canonical_contents.id"), nullable=True)

    # Object name for the standardized PDF representation in Minio
    pdf_object_name = Column(String, nullable=True)

    original_filename = Column(String, nullable=False)
    uploaded_by = Column(UUIDChar, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_accessed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    status = Column(
        SQLAlchemyEnum(DocumentStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=DocumentStatus.UPLOADED, 
        nullable=False
    )
    chunking_cursor = Column(Integer, default=0)
    tagging_cursor = Column(Integer, default=0)

    # Self-referencing FK for container relationship
    parent_document_id = Column(UUIDChar, ForeignKey("documents.id"), nullable=True)

    # --- Composite Unique Constraint ---
    __table_args__ = (
        UniqueConstraint('knowledge_space_id', 'canonical_content_id', name='_ks_canonical_content_uc'),
    )

    # --- Relationships ---
    uploader = relationship("User")
    knowledge_space = relationship("KnowledgeSpace", back_populates="documents")

    # Relationship to the Original record
    original = relationship("Original")

    # One-to-one relationship with the canonical content
    canonical_content = relationship(
        "CanonicalContent",
        uselist=False,
        cascade="all, delete-orphan",
        single_parent=True,
    )

    # One-to-many relationship to the context table, replacing the old asset_links
    asset_contexts = relationship("DocumentAssetContext", back_populates="document", cascade="all, delete-orphan")

    # One-to-many relationship with chunks
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")

    # Relationship for parent-child documents (container relationship)
    parent = relationship("Document", remote_side=[id], backref=backref('children', cascade="all, delete-orphan"))

    # One-to-many relationship with jobs
    jobs = relationship("Job", back_populates="document", cascade="all, delete-orphan")
