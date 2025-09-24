import uuid
from sqlalchemy import Column, ForeignKey, PrimaryKeyConstraint
from .base import Base, UUIDChar

class ChunkOntologyNodeLink(Base):
    """
    Represents the many-to-many relationship between a Chunk and an OntologyNode.
    This table effectively stores the 'tags' for each chunk.
    """
    __tablename__ = "chunk_ontology_node_links"

    chunk_id = Column(UUIDChar, ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False)
    node_id = Column(UUIDChar, ForeignKey("ontology_nodes.id", ondelete="CASCADE"), nullable=False)
    
    # We could add metadata here in the future, e.g., confidence_score, tagged_by_model, etc.

    __table_args__ = (
        PrimaryKeyConstraint('chunk_id', 'node_id'),
    )
