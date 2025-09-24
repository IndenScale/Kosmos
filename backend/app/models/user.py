import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import relationship
from ..models.base import Base, UUIDChar

class User(Base):
    __tablename__ = "users"

    id = Column(UUIDChar, primary_key=True, default=uuid.uuid4)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    display_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="user", nullable=False) # e.g., "super_admin", "admin", "user"
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    @property
    def user_id(self):
        return self.id

    # Relationship to the KnowledgeSpaceMember association table
    memberships = relationship("KnowledgeSpaceMember", back_populates="user")

    # Relationship to the ModelCredential table
    credentials = relationship("ModelCredential", back_populates="owner", cascade="all, delete-orphan")

