from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.db.database import Base

class Chunk(Base):
    """文档片段表"""
    __tablename__ = "chunks"

    id = Column(String, primary_key=True)  # UUID
    kb_id = Column(String, ForeignKey("knowledge_bases.id"), nullable=False)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)  # 在文档中的顺序
    content = Column(Text, nullable=False)  # 片段的文本内容 (Markdown格式)
    tags = Column(Text, nullable=False)  # LLM生成的标签 (JSON数组格式)
    created_at = Column(DateTime, default=func.now())

class IngestionJob(Base):
    """摄入任务表"""
    __tablename__ = "ingestion_jobs"

    id = Column(String, primary_key=True)  # UUID
    kb_id = Column(String, ForeignKey("knowledge_bases.id"), nullable=False)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    status = Column(String, nullable=False)  # 'pending', 'processing', 'completed', 'failed'
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())