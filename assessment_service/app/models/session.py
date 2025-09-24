"""
Data model for an Assessment Session.

A session is a short-lived, stateful workflow that processes a subset of
findings from a larger AssessmentJob. It is the primary unit of work for an
agent and is designed to be observable and controllable.
"""
import datetime
import uuid
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Table, JSON
)
from sqlalchemy.orm import relationship

# This Base should be shared across all model files.
from .base import Base, UUIDChar

class AssessmentSession(Base):
    """

    Represents a single work session within an AssessmentJob.
    This is the central object for the FSM and agent control.
    It replaces the old AssessmentBatch model.
    """
    __tablename__ = 'assessment_sessions'

    id = Column(UUIDChar, primary_key=True, default=uuid.uuid4)
    job_id = Column(UUIDChar, ForeignKey('assessment_jobs.id'), nullable=False)
    
    # FSM state field
    status = Column(String, default='READY_FOR_ASSESSMENT', nullable=False, index=True)
    
    # Link to a detailed log file in object storage (e.g., S3, MinIO)
    log_file_url = Column(String, nullable=True)
    
    # Counters and limits for agent behavior control
    action_count = Column(Integer, default=0)
    action_limit = Column(Integer, nullable=False)
    error_count = Column(Integer, default=0)
    error_limit = Column(Integer, default=5)
    warning_count = Column(Integer, default=0)
    warning_limit = Column(Integer, default=10)

    # Timestamping and timeout control
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    timeout_seconds = Column(Integer, default=3600, nullable=False)

    # Relationships
    job = relationship("AssessmentJob", back_populates="sessions")
    
    # One-to-many relationship to the specific findings this session is tasked with
    findings = relationship("AssessmentFinding", back_populates="session", cascade="all, delete-orphan")
    
    action_logs = relationship("ActionLog", back_populates="session", cascade="all, delete-orphan")
    queue_entry = relationship("ExecutionQueue", uselist=False, back_populates="session", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<AssessmentSession(id={self.id}, job_id='{self.job_id}', status='{self.status}')>"
        
    # Helper methods for FSM state checks
    def is_status_READY_FOR_ASSESSMENT(self):
        return self.status == 'READY_FOR_ASSESSMENT'
        
    def is_status_ASSESSING_CONTROLS(self):
        return self.status == 'ASSESSING_CONTROLS'
        
    def is_status_SUBMITTED_FOR_REVIEW(self):
        return self.status == 'SUBMITTED_FOR_REVIEW'
        
    def is_status_COMPLETED(self):
        return self.status == 'COMPLETED'
        
    def is_status_FAILED(self):
        return self.status == 'FAILED'
        
    def is_status_ABANDONED(self):
        return self.status == 'ABANDONED'

class ActionLog(Base):
    """
    Records an action taken by an agent within a session for audit purposes.
    """
    __tablename__ = 'action_logs'

    id = Column(UUIDChar, primary_key=True, default=uuid.uuid4)
    session_id = Column(UUIDChar, ForeignKey('assessment_sessions.id'), nullable=False)
    
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    action_type = Column(String, nullable=False)  # e.g., "search", "read"
    parameters = Column(JSON, nullable=False)     # e.g., {"query": "firewall config"}
    
    # Optional: A brief summary of the result, e.g., {"hits": 5} or {"lines_read": 10}
    result_summary = Column(JSON, nullable=True)

    session = relationship("AssessmentSession", back_populates="action_logs")

    def __repr__(self):
        return f"<ActionLog(id={self.id}, session_id={self.session_id}, action='{self.action_type}')>"
