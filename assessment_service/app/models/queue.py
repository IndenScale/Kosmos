"""
SQLAlchemy model for the Execution Queue.
"""
import uuid
from sqlalchemy import Column, String, DateTime, func, ForeignKey, Integer, JSON
from sqlalchemy.orm import relationship
from .base import Base, UUIDChar

class ExecutionQueue(Base):
    __tablename__ = "execution_queue"

    id = Column(UUIDChar, primary_key=True, default=uuid.uuid4)
    session_id = Column(UUIDChar, ForeignKey("assessment_sessions.id"), nullable=False, index=True)
    job_id = Column(UUIDChar, ForeignKey("assessment_jobs.id"), nullable=False, index=True)
    
    status = Column(String(50), nullable=False, default="PENDING", index=True)
    priority = Column(Integer, nullable=False, default=0)
    
    # Store the specific execution settings for this job run
    execution_config = Column(JSON, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    session = relationship("AssessmentSession", back_populates="queue_entry")
    job = relationship("AssessmentJob")

    def __repr__(self):
        return f"<ExecutionQueue(id={self.id}, session_id={self.session_id}, status='{self.status}')>"
