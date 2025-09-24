import uuid
from sqlalchemy import Column, String, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship
from ..models.base import Base, UUIDChar


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(UUIDChar, primary_key=True, default=uuid.uuid4)
    document_id = Column(UUIDChar, ForeignKey("documents.id"), nullable=False, index=True)
    parent_id = Column(UUIDChar, ForeignKey("chunks.id"))
    type = Column(String, nullable=False)  # "heading" or "content"
    level = Column(Integer, default=-1)
    start_line = Column(Integer)
    end_line = Column(Integer)
    char_count = Column(Integer)
    raw_content = Column(Text)
    summary = Column(Text)
    paraphrase = Column(Text)
    # The old 'tags' column is now replaced by the 'ontology_tags' relationship
    indexing_status = Column(String, default="pending", nullable=False, index=True)

    # --- Relationships ---
    document = relationship("Document", back_populates="chunks")

    # Self-referential for parent/child relationships
    parent = relationship("Chunk", remote_side=[id], back_populates="children")
    children = relationship("Chunk", back_populates="parent")

    # Many-to-many relationship with Asset
    assets = relationship("Asset", secondary="chunk_asset_links", back_populates="chunks")

    # Many-to-many relationship with OntologyNode (Tags)
    ontology_tags = relationship("OntologyNode", secondary="chunk_ontology_node_links", back_populates="chunks")
