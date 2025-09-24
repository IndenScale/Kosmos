"""
This module contains the core SQLAlchemy model for storing domain events
in the database, following the Transactional Outbox Pattern.
"""
import uuid
import enum
import json
from sqlalchemy import Column, String, DateTime, Enum as SQLAlchemyEnum, Text
from sqlalchemy.sql import func
from ..base import Base, UUIDChar


class EventStatus(str, enum.Enum):
    """Represents the processing status of a domain event."""
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"
    ABORTED = "aborted"  # 由用户或规则中止，区别于执行失败


class DomainEvent(Base):
    """
    Represents a domain event record to be stored in the database.
    
    This model acts as an "outbox" table to ensure that events are created
    atomically within the same transaction as the business logic that
    triggers them. A separate relay process will then publish these events
    to a message broker.
    """
    __tablename__ = "domain_events"

    id = Column(UUIDChar, primary_key=True, default=uuid.uuid4)
    
    # A unique identifier for the transaction or operation that created the event.
    correlation_id = Column(UUIDChar, nullable=True, index=True)

    # The ID of the aggregate root that the event pertains to (e.g., document_id).
    aggregate_id = Column(String, nullable=False, index=True)
    
    event_type = Column(String, nullable=False, index=True)
    payload = Column(Text, nullable=False)
    
    status = Column(SQLAlchemyEnum(EventStatus), default=EventStatus.PENDING, nullable=False, index=True)
    
    created_at = Column(DateTime, server_default=func.now())
    processed_at = Column(DateTime, nullable=True)
    
    error_message = Column(Text, nullable=True)
