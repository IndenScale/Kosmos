#app/models/knowledge_base.py
import sys
import os
import logging
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base
from app.utils.db_types import JSONEncodedDict
import uuid
import enum

# 配置日志
logger = logging.getLogger(__name__)

class KBRole(enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"

class KnowledgeBase(Base):
    __tablename__ = 'knowledge_bases'
    __table_args__ = {'extend_existing': True}

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(Text)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False)
    tag_dictionary = Column(JSONEncodedDict, default={})  # 标签字典配置
    search_config = Column(JSONEncodedDict, default={})  # 搜索配置（权重、top_k等）
    milvus_collection_id = Column(String, nullable=True)
    is_public = Column(Boolean, default=False)
    last_tag_dictionary_update_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # 关系
    owner = relationship("User", back_populates="owned_kbs")
    members = relationship("KBMember", back_populates="knowledge_base", cascade="all, delete-orphan")
    model_config = relationship("KBModelConfig", back_populates="knowledge_base", uselist=False, cascade="all, delete-orphan")

class KBMember(Base):
    __tablename__ = "kb_members"
    __table_args__ = {'extend_existing': True}
    kb_id = Column(String, ForeignKey("knowledge_bases.id"), primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    role = Column(String, nullable=False)  # 'owner', 'admin', 'member'
    created_at = Column(DateTime, default=func.now())

    # 关系
    knowledge_base = relationship("KnowledgeBase", back_populates="members")
    user = relationship("User", back_populates="kb_memberships")