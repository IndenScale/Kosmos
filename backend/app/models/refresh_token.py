import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean
from .base import Base, UUIDChar

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(UUIDChar, primary_key=True, default=uuid.uuid4)
    token = Column(String, nullable=False, unique=True, index=True)
    user_id = Column(UUIDChar, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)
