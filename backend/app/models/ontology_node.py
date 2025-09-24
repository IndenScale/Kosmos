import uuid
from sqlalchemy import Column, String, JSON, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base, UUIDChar

class OntologyNode(Base):
    __tablename__ = "ontology_nodes"

    id = Column(UUIDChar, primary_key=True, default=uuid.uuid4)
    knowledge_space_id = Column(UUIDChar, ForeignKey("knowledge_spaces.id"), nullable=False)

    # Stable identifier to track a concept across different versions
    stable_id = Column(UUIDChar, default=uuid.uuid4, nullable=False, index=True)

    name = Column(String, nullable=False)
    constraints = Column(JSON, nullable=True)
    node_metadata = Column(JSON, nullable=True)

    # Content hash for quick identification of identical nodes (deduplication)
    content_hash = Column(String, nullable=False, index=True)

    # --- Relationships ---
    knowledge_space = relationship("KnowledgeSpace")
    versions = relationship(
        "OntologyVersion",
        secondary="ontology_version_node_links",
        primaryjoin="OntologyNode.id == OntologyVersionNodeLink.node_id",
        secondaryjoin="OntologyVersion.id == OntologyVersionNodeLink.version_id",
        back_populates="nodes"
    )

    # Many-to-many relationship with Chunk (shows which chunks are tagged with this node)
    chunks = relationship("Chunk", secondary="chunk_ontology_node_links", back_populates="ontology_tags")
