#app/models/knowledge_base.py
import sys
print(f"DEBUG: module {__name__} is being loaded. sys.modules['{__name__}'] is: {sys.modules.get(__name__)}")
import sys
import os

# 获取当前文件的完整路径
current_file_path = os.path.abspath(__file__)

print(f"DEBUG: app/models/knowledge_base.py 模块开始加载 (文件: {current_file_path}).")
print(f"DEBUG: sys.path: {sys.path}")
print(f"DEBUG: sys.modules contains 'app.models.knowledge_base': {'app.models.knowledge_base' in sys.modules}")
print(f"DEBUG: sys.modules['app.models.knowledge_base'] is: {sys.modules.get('app.models.knowledge_base')}")


from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text,TypeDecorator, TEXT
from sqlalchemy.types import JSON
import json
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base
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
            if isinstance(value, dict):
                return json.dumps(value, ensure_ascii=False)
            elif isinstance(value, str):
                # 如果已经是字符串，先验证是否为有效JSON
                try:
                    json.loads(value)
                    return value
                except (json.JSONDecodeError, TypeError):
                    return "{}"
            else:
                return "{}"
        return "{}"

    def process_result_value(self, value, dialect):
        if value:
            try:
                return json.loads(value)
            except (TypeError, json.JSONDecodeError):
                return {}
        return {}

class KnowledgeBase(Base):
    __tablename__ = 'knowledge_bases'
    __table_args__ = {'extend_existing': True}  # 添加这行解决表重复定义问题

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
print("DEBUG: Defining KnowledgeBase class...") # <-- 添加这行
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

print("DEBUG: Defining KBMember class...") # <-- 添加这行