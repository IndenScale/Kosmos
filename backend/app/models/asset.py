import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Enum
from sqlalchemy.orm import relationship
from ..models.base import Base, UUIDChar

class AssetAnalysisStatus(str, enum.Enum):
    not_analyzed = "not_analyzed"
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"

class AssetType(str, enum.Enum):
    figure = "figure"
    table = "table"
    audio = "audio"
    video = "video"
    # Add other asset types as needed

class Asset(Base):
    __tablename__ = "assets"

    id = Column(UUIDChar, primary_key=True, default=uuid.uuid4)
    asset_hash = Column(String, nullable=False, unique=True, index=True)
    
    asset_type = Column(
        Enum(AssetType, name='asset_types_enum', create_type=False), 
        nullable=False
    )
    
    file_type = Column(String, nullable=False)
    size = Column(Integer, nullable=False)
    storage_path = Column(String, nullable=False, unique=True)
    reference_count = Column(Integer, default=1, nullable=False)
    
    analysis_status = Column(
        Enum(AssetAnalysisStatus, name='asset_analysis_status_enum', create_type=True),
        nullable=False,
        default=AssetAnalysisStatus.not_analyzed,
        server_default=AssetAnalysisStatus.not_analyzed.value,
        index=True
    )
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_accessed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # One-to-many relationship to the context table
    document_contexts = relationship("DocumentAssetContext", back_populates="asset", cascade="all, delete-orphan")
    
    # Many-to-many relationship with Chunk
    chunks = relationship("Chunk", secondary="chunk_asset_links", back_populates="assets")
