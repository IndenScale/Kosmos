"""
Data models for the dynamic assessment entities: Jobs, Findings, and Evidence.

These models capture the state and results of a specific assessment run against
a particular knowledge space, based on a chosen framework.
"""
import datetime
import uuid
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, JSON, ForeignKey, Table
)
from sqlalchemy.orm import relationship

# This Base should be shared across all model files.
from .base import Base, UUIDChar



class AssessmentJob(Base):
    """

    Represents a single, long-running assessment job.
    A job is defined by the framework it uses and the knowledge spaces it targets and references.
    """
    __tablename__ = 'assessment_jobs'

    id = Column(UUIDChar, primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=True) # A user-friendly name for the job
    
    framework_id = Column(UUIDChar, ForeignKey('assessment_frameworks.id'), nullable=False)
    
    # Overall status of the job
    status = Column(String, default='PENDING', nullable=False, index=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.datetime.utcnow)

    # Relationships
    findings = relationship("AssessmentFinding", back_populates="job", cascade="all, delete-orphan")
    sessions = relationship("AssessmentSession", back_populates="job", cascade="all, delete-orphan")
    knowledge_spaces = relationship(
        "KnowledgeSpaceLink",
        back_populates="job",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<AssessmentJob(id={self.id}, name='{self.name}', status='{self.status}')>"

class KnowledgeSpaceLink(Base):
    __tablename__ = 'job_knowledge_space_link'
    job_id = Column(UUIDChar, ForeignKey('assessment_jobs.id'), primary_key=True)
    ks_id = Column(String, primary_key=True)
    role = Column(String, nullable=False)

    job = relationship("AssessmentJob", back_populates="knowledge_spaces")


class AssessmentFinding(Base):
    """
    Represents the finding for a single control item within a specific assessment job.
    This is the "instance" of a ControlItemDefinition for a job.
    """
    __tablename__ = 'assessment_findings'

    id = Column(UUIDChar, primary_key=True, default=uuid.uuid4)
    job_id = Column(UUIDChar, ForeignKey('assessment_jobs.id'), nullable=False)
    
    # Link to the static definition of the control item
    control_item_def_id = Column(UUIDChar, ForeignKey('control_item_definitions.id'), nullable=False)
    
    # Link to the session that is currently processing this finding
    session_id = Column(UUIDChar, ForeignKey('assessment_sessions.id'), nullable=True, index=True)

    # The actual assessment results
    judgement = Column(String, nullable=True) # e.g., 'Compliant', 'Non-compliant'
    comment = Column(Text, nullable=True)
    supplement = Column(Text, nullable=True)

    # Relationships
    job = relationship("AssessmentJob", back_populates="findings")
    control_item_definition = relationship("ControlItemDefinition") # One-way for now
    evidences = relationship("Evidence", back_populates="finding", cascade="all, delete-orphan")
    session = relationship("AssessmentSession", back_populates="findings")

    def __repr__(self):
        return f"<AssessmentFinding(id={self.id}, job_id={self.job_id}, judgement='{self.judgement}')>"


class Evidence(Base):
    """
    Represents a piece of evidence (a document snippet) that supports a finding.
    """
    __tablename__ = 'evidences'

    id = Column(UUIDChar, primary_key=True, default=uuid.uuid4)
    finding_id = Column(UUIDChar, ForeignKey('assessment_findings.id'), nullable=False)
    
    doc_id = Column(String, nullable=False)
    start_line = Column(Integer, nullable=False)
    end_line = Column(Integer, nullable=False)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationship
    finding = relationship("AssessmentFinding", back_populates="evidences")

    def __repr__(self):
        return f"<Evidence(id={self.id}, doc_id='{self.doc_id}', lines={self.start_line}-{self.end_line})>"