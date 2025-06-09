from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.db.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="user")  # 'system_admin' or 'user'
    created_at = Column(DateTime, default=func.now())
    is_active = Column(Boolean, default=True)

    # 关系
    owned_kbs = relationship("KnowledgeBase", back_populates="owner")
    kb_memberships = relationship("KBMember", back_populates="user")


# 在文件末尾添加
from app.models.document import Document, KBDocument