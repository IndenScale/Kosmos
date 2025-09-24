import uuid
from sqlalchemy import Column, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import relationship
from .base import Base, UUIDChar

class OntologyVersionNodeLink(Base):
    __tablename__ = "ontology_version_node_links"

    version_id = Column(UUIDChar, ForeignKey("ontology_versions.id", ondelete="CASCADE"), nullable=False)
    node_id = Column(UUIDChar, ForeignKey("ontology_nodes.id", ondelete="CASCADE"), nullable=False)
    
    # Stores the parent_id of this node *within this specific version*, thus building the hierarchy.
    parent_node_id = Column(UUIDChar, ForeignKey("ontology_nodes.id"), nullable=True)

    # --- Relationships ---
    node = relationship("OntologyNode", foreign_keys=[node_id], viewonly=True)

    __table_args__ = (
        PrimaryKeyConstraint('version_id', 'node_id'),
    )
