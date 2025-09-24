"""
Data models for the Declarative Workflow System.

These models represent the runtime state of a workflow instance and its
constituent tasks.
"""
import uuid
from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    Enum as SQLAlchemyEnum,
    JSON,
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
import enum

from ..services.workflows.definitions import TaskType # Using the future location
from .base import UUIDChar

Base = declarative_base()

class WorkflowStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class Workflow(Base):
    __tablename__ = "workflows"

    id = Column(UUIDChar, primary_key=True, default=uuid.uuid4)
    document_id = Column(UUIDChar, ForeignKey("documents.id"), nullable=True, index=True)
    # Could also be linked to other entities like asset_id or knowledge_space_id
    
    status = Column(SQLAlchemyEnum(WorkflowStatus), nullable=False, default=WorkflowStatus.PENDING, index=True)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    tasks = relationship("Task", back_populates="workflow", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Workflow(id={self.id}, status='{self.status}')>"

class Task(Base):
    __tablename__ = "tasks"

    id = Column(UUIDChar, primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUIDChar, ForeignKey("workflows.id"), nullable=False, index=True)
    
    task_type = Column(SQLAlchemyEnum(TaskType), nullable=False)
    status = Column(SQLAlchemyEnum(TaskStatus), nullable=False, default=TaskStatus.PENDING, index=True)
    
    input_params = Column(JSON, nullable=True)
    result = Column(JSON, nullable=True)
    error_message = Column(String, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    workflow = relationship("Workflow", back_populates="tasks")

    def __repr__(self):
        return f"<Task(id={self.id}, type='{self.task_type}', status='{self.status}')>"
