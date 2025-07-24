# app/models/fragment.py

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.sql import func
from app.db.database import Base
import uuid

class Fragment(Base):
    """文档片段基类 (稳固的能指层)"""
    __tablename__ = "fragments"
    __table_args__ = (
        UniqueConstraint('content_hash', 'fragment_index', name='uq_fragment_hash_index'), # 确保同一物理文件的片段索引唯一
        {'extend_existing': True}
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))  # UUID, Fragment的唯一标识符

    # Fragment 关联到 PhysicalFile (稳固的物理关联)
    # 这是 Fragment 的核心关联，决定了 Fragment 的内容来源
    content_hash = Column(String, ForeignKey("physical_files.content_hash"), nullable=False)

    # 辅助字段：关联到具体的 Document 记录 (逻辑文件)
    # 方便查询：给定一个 Document ID，快速找到其 Fragments
    # 注意：这不是 Fragment 的主要身份标识，主要身份由 content_hash 确定
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)


    fragment_index = Column(Integer, nullable=False)  # 在文档中的顺序
    fragment_type = Column(String, nullable=False)  # 'text', 'screenshot', 'figure'

    # 可选的原始内容 (如文本内容、文件路径/URI)
    raw_content = Column(Text, nullable=True)

    # 可选的元数据 (JSON格式)，用于存储类型特定信息
    # 例如:
    #   TextFragment: {"source_pages": [1, 2]}
    #   ScreenshotFragment: {"page_number": 1, "width": 1024, "height": 768}
    #   FigureFragment: {"page_number": 2, "description": "流程图展示了...", "source_screenshot_id": "..."}
    # 注意：不能使用 'metadata' 作为列名，因为它是 SQLAlchemy 的保留字
    meta_info = Column(Text, nullable=True, name="metadata") 

    # 注意: 不再直接包含 kb_id 和 tags

    created_at = Column(DateTime, default=func.now())

    # 可以考虑添加一个 relationship 到 PhysicalFile
    # physical_file = relationship("PhysicalFile", back_populates="fragments") 
    # (需要在 PhysicalFile 中也添加对应的 relationship)

# TextFragment, ScreenshotFragment, FigureFragment 作为 Fragment 的具体类型，
# 主要通过 fragment_type 字段和 meta_info 字段来区分和存储特有信息。
# 应用层可以通过 fragment_type 来实例化具体的 Fragment 对象。


# 新增关联表：记录 Fragment 与 Knowledge Base 的关系
# 这份信息存储在 SQL 中，保证了即使 Milvus 索引丢失，也能知道哪些 Fragment 属于哪个 KB
class KBFragment(Base):
    """
    知识库-文档片段关联表
    存储在 SQL 中，作为 Milvus 索引的补充和后备。
    """
    __tablename__ = "kb_fragments"
    __table_args__ = (
        # 确保一个 Fragment 不会重复添加到同一个 KB
        UniqueConstraint('kb_id', 'fragment_id', name='uq_kb_fragment'),
        {'extend_existing': True}
    )

    kb_id = Column(String, ForeignKey("knowledge_bases.id"), primary_key=True)
    fragment_id = Column(String, ForeignKey("fragments.id"), primary_key=True)
    
    # 可以添加一些额外信息
    added_at = Column(DateTime, default=func.now()) # 添加到 KB 的时间
    # last_indexed_at = Column(DateTime, nullable=True) # 可选：上次在 Milvus 索引的时间

    # Relationships (可选)
    # knowledge_base = relationship("KnowledgeBase", back_populates="kb_fragments")
    # fragment = relationship("Fragment", back_populates="kb_entries")