import hashlib
import os
from pathlib import Path
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models.document import Document, KBDocument
from typing import List, Optional
import mimetypes

class DocumentService:
    def __init__(self, db: Session):
        self.db = db
        self.doc_repo = DocumentRepository(db)
        self.storage_path = Path("data/documents")
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def _calculate_file_hash(self, content: bytes) -> str:
        """计算文件内容的SHA256哈希值"""
        return hashlib.sha256(content).hexdigest()

    def _save_file(self, content: bytes, file_hash: str, original_filename: str) -> str:
        """保存文件到存储路径"""
        # 获取文件扩展名
        file_ext = Path(original_filename).suffix
        # 使用哈希值作为文件名
        filename = f"{file_hash}{file_ext}"
        file_path = self.storage_path / filename

        with open(file_path, "wb") as f:
            f.write(content)

        return str(file_path)

    def upload_document(self, kb_id: str, user_id: str, uploaded_file: UploadFile) -> Document:
        """上传文档到知识库"""
        # 读取文件内容
        content = uploaded_file.file.read()
        uploaded_file.file.seek(0)  # 重置文件指针

        # 计算文件哈希
        file_hash = self._calculate_file_hash(content)

        # 检查文档是否已存在
        existing_doc = self.doc_repo.get_document_by_id(file_hash)

        if existing_doc:
            # 文档已存在，只需创建关联
            try:
                self.doc_repo.link_document_to_kb(kb_id, file_hash, user_id)
                return existing_doc
            except Exception as e:
                if "UNIQUE constraint failed" in str(e):
                    raise HTTPException(status_code=400, detail="文档已存在于该知识库中")
                raise e
        else:
            # 新文档，需要保存文件并创建记录
            try:
                # 保存文件
                file_path = self._save_file(content, file_hash, uploaded_file.filename)

                # 获取MIME类型
                mime_type, _ = mimetypes.guess_type(uploaded_file.filename)
                if not mime_type:
                    mime_type = uploaded_file.content_type or "application/octet-stream"

                # 在事务中创建文档记录和关联
                doc_data = {
                    "id": file_hash,
                    "filename": uploaded_file.filename,
                    "file_type": mime_type,
                    "file_size": len(content),
                    "file_path": file_path
                }

                document = self.doc_repo.create_document(doc_data)
                self.doc_repo.link_document_to_kb(kb_id, file_hash, user_id)

                return document

            except Exception as e:
                # 如果创建失败，清理已保存的文件
                if 'file_path' in locals() and os.path.exists(file_path):
                    os.remove(file_path)
                raise e

    def get_kb_documents(self, kb_id: str) -> List[KBDocument]:
        """获取知识库中的所有文档"""
        return self.doc_repo.get_kb_documents(kb_id)

    def get_kb_document(self, kb_id: str, document_id: str) -> Optional[KBDocument]:
        """获取知识库中的特定文档"""
        return self.doc_repo.get_kb_document(kb_id, document_id)

    def get_document_file_path(self, document_id: str) -> Optional[str]:
        """获取文档的文件路径"""
        document = self.doc_repo.get_document_by_id(document_id)
        if document and os.path.exists(document.file_path):
            return document.file_path
        return None

    def remove_document_from_kb(self, kb_id: str, document_id: str) -> bool:
        """从知识库中移除文档"""
        success = self.doc_repo.remove_document_from_kb(kb_id, document_id)

        if success:
            # 检查文档是否还被其他知识库引用
            if not self.doc_repo.is_document_referenced(document_id):
                # 如果没有其他引用，可以删除物理文件和文档记录
                document = self.doc_repo.get_document_by_id(document_id)
                if document:
                    # 删除物理文件
                    if os.path.exists(document.file_path):
                        os.remove(document.file_path)
                    # 删除文档记录
                    self.db.delete(document)
                    self.db.commit()

        return success


class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_document_by_id(self, doc_id: str) -> Optional[Document]:
        """根据ID获取文档"""
        return self.db.query(Document).filter(Document.id == doc_id).first()

    def create_document(self, doc_data: dict) -> Document:
        """创建新文档记录"""
        document = Document(**doc_data)
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def link_document_to_kb(self, kb_id: str, document_id: str, uploaded_by: str) -> KBDocument:
        """将文档关联到知识库"""
        kb_doc = KBDocument(
            kb_id=kb_id,
            document_id=document_id,
            uploaded_by=uploaded_by
        )
        self.db.add(kb_doc)
        self.db.commit()
        self.db.refresh(kb_doc)
        return kb_doc

    def get_kb_documents(self, kb_id: str) -> List[KBDocument]:
        """获取知识库中的所有文档"""
        return self.db.query(KBDocument).filter(KBDocument.kb_id == kb_id).all()

    def get_kb_document(self, kb_id: str, document_id: str) -> Optional[KBDocument]:
        """获取知识库中的特定文档"""
        return self.db.query(KBDocument).filter(
            and_(KBDocument.kb_id == kb_id, KBDocument.document_id == document_id)
        ).first()

    def remove_document_from_kb(self, kb_id: str, document_id: str) -> bool:
        """从知识库中移除文档"""
        kb_doc = self.get_kb_document(kb_id, document_id)
        if kb_doc:
            self.db.delete(kb_doc)
            self.db.commit()
            return True
        return False

    def is_document_referenced(self, document_id: str) -> bool:
        """检查文档是否还被其他知识库引用"""
        count = self.db.query(KBDocument).filter(KBDocument.document_id == document_id).count()
        return count > 0