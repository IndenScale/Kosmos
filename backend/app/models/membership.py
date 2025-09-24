import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from ..models.base import Base, UUIDChar

class KnowledgeSpaceMember(Base):
    __tablename__ = "knowledge_space_members"

    id = Column(UUIDChar, primary_key=True, default=uuid.uuid4)
    knowledge_space_id = Column(UUIDChar, ForeignKey("knowledge_spaces.id"), nullable=False)
    user_id = Column(UUIDChar, ForeignKey("users.id"), nullable=False)
    role = Column(String, nullable=False, default="viewer")  # e.g., "owner", "editor", "viewer"
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships to easily access related objects
    user = relationship("User")
    knowledge_space = relationship("KnowledgeSpace")

    # Ensure a user can only be a member of a space once
    __table_args__ = (UniqueConstraint('knowledge_space_id', 'user_id', name='_knowledge_space_user_uc'),)
