
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, UUIDChar

class Bookmark(Base):
    __tablename__ = "bookmarks"

    id: Mapped[uuid.UUID] = mapped_column(UUIDChar, primary_key=True, default=uuid.uuid4)
    
    # --- Hierarchy ---
    parent_id: Mapped[uuid.UUID] = mapped_column(UUIDChar, ForeignKey("bookmarks.id"), nullable=True)

    # --- Core Attributes ---
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    knowledge_space_id: Mapped[uuid.UUID] = mapped_column(UUIDChar, ForeignKey("knowledge_spaces.id"), nullable=False, index=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUIDChar, ForeignKey("users.id"), nullable=False, index=True)
    visibility: Mapped[str] = mapped_column(Enum('private', 'public', name='bookmark_visibility_enum'), nullable=False, default='private', server_default='private')

    # --- Target Link (Optional) ---
    document_id: Mapped[uuid.UUID] = mapped_column(UUIDChar, ForeignKey("documents.id"), nullable=True)
    start_line: Mapped[int] = mapped_column(Integer, nullable=True)
    end_line: Mapped[int] = mapped_column(Integer, nullable=True)

    # --- Timestamps ---
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # --- Relationships ---
    knowledge_space = relationship("KnowledgeSpace")
    owner = relationship("User")
    document = relationship("Document")

    # Self-referential for parent/child relationships
    parent = relationship("Bookmark", remote_side=[id], back_populates="children")
    children = relationship("Bookmark", back_populates="parent", cascade="all, delete-orphan")

