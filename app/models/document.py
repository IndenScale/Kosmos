# app/models/document
import sys
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base
import uuid

class PhysicalFile(Base):
    """物理文件表 (按内容哈希去重)"""
    __tablename__ = "physical_files"
    
    content_hash = Column(String, primary_key=True)  # 文件内容的 SHA256 哈希值
    file_path = Column(String, nullable=False, unique=True)  # 在本地文件系统的存储路径
    file_size = Column(Integer, nullable=False)  # 文件大小 (bytes)
    created_at = Column(DateTime, default=func.now())
    reference_count = Column(Integer, default=0)  # 引用计数
    
    # 关系
    documents = relationship("Document", back_populates="physical_file")

class Document(Base):
    """文档记录表 (每次上传都是独立记录)"""
    __tablename__ = "documents"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))  # 使用UUID作为主键
    content_hash = Column(String, ForeignKey("physical_files.content_hash"), nullable=False)  # 关联到物理文件
    filename = Column(String, nullable=False)  # 上传时的原始文件名
    file_type = Column(String, nullable=False)  # MIME 类型
    uploaded_by = Column(String, ForeignKey("users.id"), nullable=False)  # 上传用户
    created_at = Column(DateTime, default=func.now())
    
    # 关系
    physical_file = relationship("PhysicalFile", back_populates="documents")
    kb_documents = relationship("KBDocument", back_populates="document", cascade="all, delete-orphan")
    uploader = relationship("User")

class KBDocument(Base):
    """知识库-文档关联表"""
    __tablename__ = "kb_documents"
    
    kb_id = Column(String, ForeignKey("knowledge_bases.id"), primary_key=True)
    document_id = Column(String, ForeignKey("documents.id"), primary_key=True)
    upload_at = Column(DateTime, default=func.now())
    last_ingest_time = Column(DateTime, nullable=True)
    
    # 关系
    knowledge_base = relationship("KnowledgeBase")
    document = relationship("Document", back_populates="kb_documents")