import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer, JSON
from sqlalchemy.orm import relationship
from .base import Base, UUIDChar

class OntologyVersion(Base):
    __tablename__ = "ontology_versions"

    id = Column(UUIDChar, primary_key=True, default=uuid.uuid4)
    ontology_id = Column(UUIDChar, ForeignKey("ontologies.id"), nullable=False)
    
    # --- Lineage ---
    parent_version_id = Column(UUIDChar, ForeignKey("ontology_versions.id"), nullable=True)
    
    # --- Audit Info ---
    version_number = Column(Integer, nullable=False)
    commit_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by_user_id = Column(UUIDChar, ForeignKey("users.id"), nullable=False)
    
    # Denormalized snapshot for quick loading
    serialized_nodes = Column(JSON, nullable=False)

    # --- Relationships ---
    ontology = relationship("Ontology", back_populates="versions", foreign_keys=[ontology_id])
    
    parent_version = relationship("OntologyVersion", remote_side=[id], back_populates="children")
    children = relationship("OntologyVersion", back_populates="parent_version")

    author = relationship("User")
    
    nodes = relationship(
        "OntologyNode",
        secondary="ontology_version_node_links",
        primaryjoin="OntologyVersion.id == OntologyVersionNodeLink.version_id",
        secondaryjoin="OntologyNode.id == OntologyVersionNodeLink.node_id",
        back_populates="versions"
    )
