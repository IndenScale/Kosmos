# app/models/fragment.py

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.sql import func
from app.db.database import Base
from app.utils.db_types import JSONEncodedDict
import uuid

class Fragment(Base):
    """文档片段基类 (稳固的能指层)"""
    __tablename__ = "fragments"
    __table_args__ = (
        UniqueConstraint('content_hash', 'fragment_index', name='uq_fragment_hash_index'),
        {'extend_existing': True}
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    content_hash = Column(String, ForeignKey("physical_documents.content_hash"), nullable=False)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    fragment_index = Column(Integer, nullable=False)
    fragment_type = Column(String, nullable=False)  # 'text', 'screenshot', 'figure'
    raw_content = Column(Text, nullable=True)
    meta_info = Column(JSONEncodedDict, nullable=True, name="metadata")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

# TextFragment, ScreenshotFragment, FigureFragment 作为 Fragment 的具体类型，
# 主要通过 fragment_type 字段和 meta_info 字段来区分和存储特有信息。
# 应用层可以通过 fragment_type 来实例化具体的 Fragment 对象。


# 新增关联表：记录 Fragment 与 Knowledge Base 的关系
# 这份信息存储在 SQL 中，保证了即使 Milvus 索引丢失，也能知道哪些 Fragment 属于哪个 KB
class KBFragment(Base):
    """知识库-文档片段关联表"""
    __tablename__ = "kb_fragments"
    __table_args__ = (
        UniqueConstraint('kb_id', 'fragment_id', name='uq_kb_fragment'),
        {'extend_existing': True}
    )

    kb_id = Column(String, ForeignKey("knowledge_bases.id"), primary_key=True)
    fragment_id = Column(String, ForeignKey("fragments.id"), primary_key=True)
    added_at = Column(DateTime, default=func.now())