from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from models.user import Base

class Document(Base):
    """原始文档表 (全局唯一)"""
    __tablename__ = "documents"

    id = Column(String, primary_key=True)  # 文件内容的 SHA256 哈希值
    filename = Column(String, nullable=False)  # 上传时的原始文件名
    file_type = Column(String, nullable=False)  # MIME 类型
    file_size = Column(Integer, nullable=False)  # 文件大小 (bytes)
    file_path = Column(String, nullable=False, unique=True)  # 在本地文件系统的存储路径
    created_at = Column(DateTime, default=func.now())

    # 关系
    kb_documents = relationship("KBDocument", back_populates="document", cascade="all, delete-orphan")

class KBDocument(Base):
    """知识库-文档关联表"""
    __tablename__ = "kb_documents"

    kb_id = Column(String, ForeignKey("knowledge_bases.id"), primary_key=True)
    document_id = Column(String, ForeignKey("documents.id"), primary_key=True)
    uploaded_by = Column(String, ForeignKey("users.id"), nullable=False)
    upload_at = Column(DateTime, default=func.now())

    # 关系
    knowledge_base = relationship("KnowledgeBase")
    document = relationship("Document", back_populates="kb_documents")
    uploader = relationship("User")