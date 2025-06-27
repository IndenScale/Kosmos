# app/models/chunk.py
import sys
print(f"DEBUG: module {__name__} is being loaded. sys.modules['{__name__}'] is: {sys.modules.get(__name__)}")
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.db.database import Base

class Chunk(Base):
    """文档片段表"""
    __tablename__ = "chunks"
    __table_args__ = {'extend_existing': True}
    id = Column(String, primary_key=True)  # UUID
    kb_id = Column(String, ForeignKey("knowledge_bases.id"), nullable=False)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)  # 在文档中的顺序
    content = Column(Text, nullable=False)  # 片段的文本内容 (Markdown格式)
    tags = Column(Text, nullable=False)  # LLM生成的标签 (JSON数组格式)
    page_screenshot_ids = Column(Text, nullable=True)  # 关联的页面截图ID列表 (JSON数组格式)
    created_at = Column(DateTime, default=func.now())

class IngestionJob(Base):
    """摄入任务表"""
    __tablename__ = "ingestion_jobs"
    __table_args__ = {'extend_existing': True}
    id = Column(String, primary_key=True)  # UUID
    kb_id = Column(String, ForeignKey("knowledge_bases.id"), nullable=False)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    task_id = Column(String, nullable=True)  # 队列任务ID
    status = Column(String, nullable=False)  # 'pending', 'processing', 'completed', 'failed'
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())