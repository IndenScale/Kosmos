"""
Data models for the static assessment assets: Frameworks and Control Item Definitions.

These models represent the "master list" of assessment criteria and are not
tied to a specific assessment job. They are the source of truth for what
needs to be assessed.
"""
import datetime
import uuid
from sqlalchemy import (
    Column, String, Text, DateTime, JSON, ForeignKey
)
from sqlalchemy.orm import relationship

# This Base should be shared across all model files.
from .base import Base, UUIDChar

class AssessmentFramework(Base):
    """
    Represents a complete assessment framework, like 'Cyber Security Level Protection 2.0'.
    This is the top-level container for a set of control items.
    """
    __tablename__ = 'assessment_frameworks'

    id = Column(UUIDChar, primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)
    version = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    source = Column(String, nullable=True) # Optional URL or reference to the source document

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.datetime.utcnow)

    # Relationship to its control items
    control_item_definitions = relationship(
        "ControlItemDefinition",
        back_populates="framework",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<AssessmentFramework(id={self.id}, name='{self.name}', version='{self.version}')>"


class ControlItemDefinition(Base):
    """
    Represents the master definition of a single control item within a framework.
    This is the "template" for an assessment finding.
    """
    __tablename__ = 'control_item_definitions'

    id = Column(UUIDChar, primary_key=True, default=uuid.uuid4)
    
    # Human-readable ID, like "7.2.1.a". Should be unique within a framework.
    display_id = Column(String, nullable=False, index=True)
    
    framework_id = Column(UUIDChar, ForeignKey('assessment_frameworks.id'), nullable=False)
    
    # Self-referencing for hierarchical structure
    parent_id = Column(UUIDChar, ForeignKey('control_item_definitions.id'), nullable=True)

    # The official, original text of the control item.
    content = Column(Text, nullable=False)
    
    # Role-specific, structured guidance for different types of agents (e.g., assessment, audit).
    # Example: {"assessment_agent": "...", "audit_agent": "..."}
    assessment_guidance = Column(JSON, nullable=True)
    
    # Flexible field for framework-specific data like 'test_procedure', 'expected_results', etc.
    details = Column(JSON, nullable=True)

    # Relationships
    framework = relationship("AssessmentFramework", back_populates="control_item_definitions")
    parent = relationship("ControlItemDefinition", remote_side=[id], back_populates="children")
    children = relationship("ControlItemDefinition", back_populates="parent")

    def __repr__(self):
        return f"<ControlItemDefinition(id={self.id}, display_id='{self.display_id}')>"
