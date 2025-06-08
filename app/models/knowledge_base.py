#app/models/knowledge_base.py

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text,TypeDecorator, TEXT
from sqlalchemy.types import JSON
import json
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from models.user import Base
import uuid
import enum

class KBRole(enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"

class JSONEncodedDict(TypeDecorator):
    """自动处理 JSON 字典与字符串的转换"""
    impl = TEXT

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = json.dumps(value, ensure_ascii=False) if value is not None else "{}"
        return value

    def process_result_value(self, value, dialect):
        try:
            return json.loads(value) if value else {}
        except (TypeError, json.JSONDecodeError):
            return {}

class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(Text)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False)
    tag_dictionary = Column(JSONEncodedDict, default={})
    # tag_dictionary = Column(JSON, nullable=False, default={})
    milvus_collection_id = Column(String, nullable=True)  # 新增字段
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())

    # 关系
    owner = relationship("User", back_populates="owned_kbs")
    members = relationship("KBMember", back_populates="knowledge_base", cascade="all, delete-orphan")

class KBMember(Base):
    __tablename__ = "kb_members"

    kb_id = Column(String, ForeignKey("knowledge_bases.id"), primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    role = Column(String, nullable=False)  # 'owner', 'admin', 'member'
    created_at = Column(DateTime, default=func.now())

    # 关系
    knowledge_base = relationship("KnowledgeBase", back_populates="members")
    user = relationship("User", back_populates="kb_memberships")