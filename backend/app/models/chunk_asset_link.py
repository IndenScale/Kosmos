import uuid
from sqlalchemy import Column, ForeignKey, PrimaryKeyConstraint
from .base import Base, UUIDChar

class ChunkAssetLink(Base):
    __tablename__ = "chunk_asset_links"

    chunk_id = Column(UUIDChar, ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False)
    asset_id = Column(UUIDChar, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint('chunk_id', 'asset_id'),
    )
