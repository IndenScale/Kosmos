# app/models/document
import sys
from sqlalchemy import Column, String, Integer, BigInteger, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base
import uuid

class PhysicalDocument(Base):
    """物理文件表 (按内容哈希去重)

    存储文件的物理信息，通过内容哈希实现去重。
    一个物理文件可以被多个Document记录引用。
    """
    __tablename__ = "physical_documents"

    phys_doc_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    content_hash = Column(String, nullable=False, unique=True, index=True)  # 文件内容的 SHA256 哈希值

    # 文件基本信息
    file_size = Column(BigInteger, nullable=False)  # 文件大小（字节）
    mime_type = Column(String(100), nullable=False)  # MIME类型
    extension = Column(String(20))  # 文件扩展名（包含点号，如 .pdf）

    # 存储信息 - 统一使用URL（支持file:///本地文件和S3/MinIO远程文件）
    url = Column(String(1024), nullable=False)  # 文件URL（file:///本地路径 或 S3/MinIO URL）

    # 元数据
    reference_count = Column(Integer, default=0, nullable=False)  # 引用计数
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # 文件特征（可选，用于后续扩展）
    encoding = Column(String(50))  # 文件编码（如 utf-8）
    language = Column(String(10))  # 检测到的主要语言

    # 关系
    documents = relationship("Document", back_populates="physical_file")

class Document(Base):
    """文档记录表 (每次上传都是独立记录)"""
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))  # 使用UUID作为主键
    content_hash = Column(String, ForeignKey("physical_documents.content_hash"), nullable=False)  # 关联到物理文件
    filename = Column(String, nullable=False)  # 上传时的原始文件名
    file_type = Column(String, nullable=False)  # MIME 类型
    uploaded_by = Column(String, ForeignKey("users.id"), nullable=False)  # 上传用户
    created_at = Column(DateTime, default=func.now())

    # 关系
    physical_file = relationship("PhysicalDocument", back_populates="documents")
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