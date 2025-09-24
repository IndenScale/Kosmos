import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.orm import relationship
from ..models.base import Base, UUIDChar

class CanonicalContent(Base):
    __tablename__ = "canonical_contents"

    # Using a UUID for the primary key is better for a 1-to-1 relationship target
    id = Column(UUIDChar, primary_key=True, default=uuid.uuid4)
    
    content_hash = Column(String, nullable=False, unique=True, index=True)
    file_type = Column(String, default="text/markdown", nullable=False)
    size = Column(Integer, nullable=False)
    storage_path = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_accessed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    page_mappings = relationship("ContentPageMapping", back_populates="canonical_content", cascade="all, delete-orphan")
