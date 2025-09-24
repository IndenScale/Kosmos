import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime
from ..models.base import Base, UUIDChar

class Original(Base):
    __tablename__ = "originals"

    id = Column(UUIDChar, primary_key=True, default=uuid.uuid4)
    original_hash = Column(String, nullable=False, unique=True, index=True)
    
    reported_file_type = Column(String, nullable=False)
    detected_mime_type = Column(String, nullable=True)
    size = Column(Integer, nullable=False)
    storage_path = Column(String, nullable=False, unique=True)
    reference_count = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_accessed_at = Column(DateTime, default=datetime.utcnow, nullable=False)