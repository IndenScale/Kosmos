import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Text, JSON, ForeignKey, Enum as SQLAlchemyEnum, DateTime
from sqlalchemy.orm import relationship, foreign
from .base import Base, UUIDChar
from .credential import CredentialType
from .document import Document
from .knowledge_space import KnowledgeSpace
from .user import User

class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ABORTED = "aborted"

class JobType(str, enum.Enum):
    CONTENT_EXTRACTION = "content_extraction"
    DOCUMENT_PROCESSING = "document_processing"
    CHUNKING = "chunking"
    TAGGING = "tagging"
    ASSET_ANALYSIS = "asset_analysis"
    INDEXING = "indexing"
    KNOWLEDGE_SPACE_BATCH_PROCESS = "knowledge_space_batch_process"

class Job(Base):
    __tablename__ = "jobs"
    id = Column(UUIDChar, primary_key=True, default=uuid.uuid4)

    # --- Core Associations ---
    document_id = Column(UUIDChar, ForeignKey("documents.id"), nullable=False, index=True)
    knowledge_space_id = Column(UUIDChar, ForeignKey("knowledge_spaces.id"), nullable=False, index=True)
    initiator_id = Column(UUIDChar, ForeignKey("users.id"), nullable=False, index=True)

    # --- Job Metadata ---
    job_type = Column(SQLAlchemyEnum(JobType), nullable=False)
    status = Column(SQLAlchemyEnum(JobStatus), default=JobStatus.PENDING, nullable=False, index=True)
    credential_type_preference = Column(SQLAlchemyEnum(CredentialType), nullable=False)

    # --- State & Context ---
    progress = Column(JSON, nullable=True, comment="e.g., {'current_line': 100, 'total_lines': 1500}")
    context = Column(JSON, nullable=True, comment="e.g., {'identified_headings': [...]}")

    # --- Result & Error ---
    result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    # --- Timestamps ---
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, comment="作业创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, comment="作业更新时间")

    # --- Relationships ---
    # [FINAL FIX] Define explicit primaryjoin conditions for all UUID-based relationships
    # to ensure correct JOIN behavior with SQLite's binary UUID storage.

    document = relationship(
        "Document",
        back_populates="jobs"
    )
    knowledge_space = relationship(
        "KnowledgeSpace",
        back_populates="jobs"
    )
    initiator = relationship(
        "User",
    )
