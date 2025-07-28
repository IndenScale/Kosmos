# app/models/index.py

import json
import uuid
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.ext.hybrid import hybrid_property
from app.db.database import Base

class Index(Base):
    """索引条目模型 (能指层的表达)"""
    __tablename__ = "index_entries"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    kb_id = Column(String, ForeignKey("knowledge_bases.id"), nullable=False)
    fragment_id = Column(String, ForeignKey("fragments.id", ondelete="CASCADE"), nullable=False)
    tags = Column(Text, nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


    @hybrid_property
    def tags_list(self):
        """
        将 tags (JSON 字符串) 转换为 Python 列表的便捷属性。
        """
        if self.tags:
            try:
                return json.loads(self.tags)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    @tags_list.setter
    def tags_list(self, value):
        """
        将 Python 列表设置为 tags (JSON 字符串)。
        """
        if value is not None:
            self.tags = json.dumps(value, ensure_ascii=False)
        else:
            self.tags = None
