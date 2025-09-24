import uuid
from sqlalchemy import Column, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base, UUIDChar

class Ontology(Base):
    __tablename__ = "ontologies"

    id = Column(UUIDChar, primary_key=True, default=uuid.uuid4)
    knowledge_space_id = Column(UUIDChar, ForeignKey("knowledge_spaces.id"), unique=True, nullable=False)
    
    # This uses a string for the foreign key to avoid circular import issues with OntologyVersion
    active_version_id = Column(UUIDChar, ForeignKey("ontology_versions.id"), nullable=True)

    # --- Relationships ---
    knowledge_space = relationship("KnowledgeSpace", back_populates="ontology")
    
    versions = relationship("OntologyVersion", 
                            back_populates="ontology", 
                            cascade="all, delete-orphan",
                            foreign_keys="[OntologyVersion.ontology_id]")
                            
    active_version = relationship("OntologyVersion", 
                                  foreign_keys=[active_version_id],
                                  post_update=True)
