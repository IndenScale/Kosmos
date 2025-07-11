#app/models/knowledge_base.py
import sys
import os
import logging
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text,TypeDecorator, TEXT
from sqlalchemy.types import JSON
import json
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base
import uuid
import enum

# 配置日志
logger = logging.getLogger(__name__)

class KBRole(enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"

class JSONEncodedDict(TypeDecorator):
    """自动处理 JSON 字典与字符串的转换"""
    impl = TEXT

    def process_bind_param(self, value, dialect):
        if value is not None:
            if isinstance(value, dict):
                try:
                    json_str = json.dumps(value, ensure_ascii=False)
                    logger.debug(f"字典序列化成功，JSON长度: {len(json_str)} 字符")
                    return json_str
                except Exception as e:
                    logger.error(f"字典序列化失败: {e}")
                    raise e
            elif isinstance(value, str):
                # 如果已经是字符串，先验证是否为有效JSON
                try:
                    parsed = json.loads(value)
                    logger.debug(f"字符串验证为有效JSON，长度: {len(value)} 字符")
                    return value
                except (json.JSONDecodeError, TypeError) as e:
                    logger.error(f"字符串不是有效JSON: {e}")
                    raise ValueError(f"无效的JSON字符串: {e}")
            else:
                logger.error(f"不支持的数据类型: {type(value)}")
                raise TypeError(f"不支持的数据类型: {type(value)}")
        
        logger.debug("输入值为None，返回空字典")
        return "{}"

    def process_result_value(self, value, dialect):
        if value:
            try:
                parsed = json.loads(value)
                logger.debug(f"JSON解析成功，字典键数: {len(parsed) if isinstance(parsed, dict) else 'N/A'}")
                return parsed
            except (TypeError, json.JSONDecodeError) as e:
                logger.error(f"JSON解析失败: {e}")
                return {}
        
        logger.debug("数据库值为空，返回空字典")
        return {}

class KnowledgeBase(Base):
    __tablename__ = 'knowledge_bases'
    __table_args__ = {'extend_existing': True}

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(Text)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False)
    tag_dictionary = Column(JSONEncodedDict, default={})
    # tag_dictionary = Column(JSON, nullable=False, default={})
    milvus_collection_id = Column(String, nullable=True)  # 新增字段
    is_public = Column(Boolean, default=False)
    last_tag_directory_update_time = Column(DateTime, nullable=True)  # 新增：标签字典最后更新时间
    created_at = Column(DateTime, default=func.now())

    # 关系
    owner = relationship("User", back_populates="owned_kbs")
    members = relationship("KBMember", back_populates="knowledge_base", cascade="all, delete-orphan")

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