from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_
from fastapi import HTTPException, UploadFile

from typing import List, Optional, Dict

import os
from pathlib import Path
import hashlib
import mimetypes
import uuid
from app.models.document import Document, KBDocument, PhysicalFile
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User
from app.repositories.document_repo import DocumentRepository
from app.repositories.chunk_repo import ChunkRepository

class DocumentService:
    def __init__(self, db: Session):
        self.db = db
        self.doc_repo = DocumentRepository(db)
        self.chunk_repo = ChunkRepository(db)
        self.storage_path = Path("data/documents")
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def _calculate_file_hash(self, content: bytes) -> str:
        """计算文件内容的SHA256哈希值"""
        return hashlib.sha256(content).hexdigest()

    def _save_physical_file(self, content: bytes, content_hash: str, original_filename: str) -> str:
        """保存物理文件到存储路径"""
        # 获取文件扩展名
        file_ext = Path(original_filename).suffix
        # 使用哈希值作为文件名
        filename = f"{content_hash}{file_ext}"
        file_path = self.storage_path / filename

        # 确保目录存在
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # 如果文件不存在才写入
        if not file_path.exists():
            with open(file_path, "wb") as f:
                f.write(content)

        # 返回标准化的路径（跨平台兼容）
        return os.path.normpath(str(file_path))

    def upload_document(self, kb_id: str, user_id: str, uploaded_file: UploadFile) -> Document:
        """上传文档到知识库"""
        # 读取文件内容
        content = uploaded_file.file.read()
        uploaded_file.file.seek(0)  # 重置文件指针

        # 计算文件哈希
        content_hash = self._calculate_file_hash(content)

        try:
            # 检查物理文件是否已存在
            physical_file = self.db.query(PhysicalFile).filter(
                PhysicalFile.content_hash == content_hash
            ).first()

            if not physical_file:
                # 保存物理文件
                file_path = self._save_physical_file(content, content_hash, uploaded_file.filename)

                # 创建物理文件记录
                physical_file = PhysicalFile(
                    content_hash=content_hash,
                    file_path=file_path,
                    file_size=len(content),
                    reference_count=0
                )
                self.db.add(physical_file)

            # 获取MIME类型
            mime_type, _ = mimetypes.guess_type(uploaded_file.filename)
            if not mime_type:
                mime_type = uploaded_file.content_type or "application/octet-stream"

            # 创建文档记录（每次上传都是新记录）
            document = Document(
                id=str(uuid.uuid4()),
                content_hash=content_hash,
                filename=uploaded_file.filename,
                file_type=mime_type,
                uploaded_by=user_id
            )
            self.db.add(document)

            # 创建知识库-文档关联
            kb_document = KBDocument(
                kb_id=kb_id,
                document_id=document.id
            )
            self.db.add(kb_document)

            # 增加物理文件引用计数
            physical_file.reference_count += 1

            self.db.commit()
            self.db.refresh(document)

            return document

        except Exception as e:
            self.db.rollback()
            # 如果创建失败且是新物理文件，清理已保存的文件
            if 'file_path' in locals() and os.path.exists(file_path) and not physical_file:
                os.remove(file_path)
            raise e

    def get_kb_documents(self, kb_id: str) -> List[KBDocument]:
        """获取知识库中的所有文档"""
        return self.doc_repo.get_kb_documents(kb_id)

    def get_kb_documents_with_chunk_count(self, kb_id: str) -> List[dict]:
        """获取知识库中的所有文档及其chunks数量"""
        # 首先获取知识库信息
        kb = self.db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
        if not kb:
            return []

        # 获取文档列表
        kb_documents = self.db.query(KBDocument).filter(
            KBDocument.kb_id == kb_id
        ).options(
            joinedload(KBDocument.document).joinedload(Document.physical_file),
            joinedload(KBDocument.document).joinedload(Document.uploader)
        ).all()

        result = []
        for kb_doc in kb_documents:
            # 判断索引是否失效
            is_index_outdated = False
            if kb.last_tag_directory_update_time and kb_doc.last_ingest_time:
                # 如果标签字典更新时间晚于文档最后摄入时间，则索引失效
                is_index_outdated = kb.last_tag_directory_update_time > kb_doc.last_ingest_time
            elif kb.last_tag_directory_update_time and not kb_doc.last_ingest_time:
                # 如果有标签字典更新但文档从未摄入，则需要摄入
                is_index_outdated = True

            chunks = self.chunk_repo.get_chunks_by_document(kb_doc.document_id)

            # 构建完整的文档数据
            doc_dict = {
                "kb_id": kb_doc.kb_id,
                "document_id": kb_doc.document_id,
                "upload_at": kb_doc.upload_at,
                "last_ingest_time": kb_doc.last_ingest_time,
                "document": {
                    "id": kb_doc.document.id,
                    "filename": kb_doc.document.filename,
                    "file_type": kb_doc.document.file_type,
                    "created_at": kb_doc.document.created_at,
                    "file_size": kb_doc.document.physical_file.file_size if kb_doc.document.physical_file else 0,
                    "file_path": kb_doc.document.physical_file.file_path if kb_doc.document.physical_file else ""
                },
                "chunk_count": len(chunks),
                "uploader_username": kb_doc.document.uploader.username if kb_doc.document.uploader else None
            }
            doc_dict["is_index_outdated"] = is_index_outdated
            result.append(doc_dict)

        return result

    def get_kb_document(self, kb_id: str, document_id: str) -> Optional[KBDocument]:
        """获取知识库中的特定文档"""
        return self.db.query(KBDocument).filter(
            and_(KBDocument.kb_id == kb_id, KBDocument.document_id == document_id)
        ).options(
            joinedload(KBDocument.document).joinedload(Document.physical_file),
            joinedload(KBDocument.document).joinedload(Document.uploader)
        ).first()

    def get_document_file_path(self, document_id: str) -> Optional[str]:
        """获取文档的文件路径"""
        # 使用joinedload预加载physical_file关系
        document = self.db.query(Document).options(
            joinedload(Document.physical_file)
        ).filter(Document.id == document_id).first()

        if document and document.physical_file:
            # 标准化路径格式以处理跨平台兼容性
            normalized_path = os.path.normpath(document.physical_file.file_path)
            if os.path.exists(normalized_path):
                return normalized_path
        return None

    def remove_document_from_kb(self, kb_id: str, document_id: str) -> bool:
        """从知识库中移除文档"""
        try:
            # 获取文档记录（预加载物理文件信息）
            document = self.db.query(Document).options(
                joinedload(Document.physical_file)
            ).filter(Document.id == document_id).first()

            if not document:
                return False

            # 删除该文档在该知识库中的所有chunks
            self.chunk_repo.delete_chunks_by_kb_and_document(kb_id, document_id)

            # 删除向量数据库中的相关向量
            from app.repositories.milvus_repo import MilvusRepository
            milvus_repo = MilvusRepository()
            milvus_repo.delete_vectors_by_document(kb_id, document_id)

            # 删除知识库-文档关联
            kb_doc = self.db.query(KBDocument).filter(
                KBDocument.kb_id == kb_id,
                KBDocument.document_id == document_id
            ).first()

            if kb_doc:
                self.db.delete(kb_doc)

                # 检查文档是否还被其他知识库引用
                other_kb_refs = self.db.query(KBDocument).filter(
                    KBDocument.document_id == document_id
                ).count()

                if other_kb_refs == 0:
                    # 删除文档记录
                    content_hash = document.content_hash
                    self.db.delete(document)

                    # 减少物理文件引用计数
                    physical_file = document.physical_file

                    if physical_file:
                        physical_file.reference_count -= 1

                        # 如果没有引用了，删除物理文件
                        if physical_file.reference_count <= 0:
                            normalized_path = os.path.normpath(physical_file.file_path)
                            if os.path.exists(normalized_path):
                                os.remove(normalized_path)
                            self.db.delete(physical_file)

                self.db.commit()
                return True

        except Exception as e:
            self.db.rollback()
            raise e

        return False

    def remove_documents_from_kb(self, kb_id: str, document_ids: List[str]) -> Dict[str, bool]:
        """批量从知识库中移除文档"""
        results = {}

        for document_id in document_ids:
            try:
                success = self.remove_document_from_kb(kb_id, document_id)
                results[document_id] = success
            except Exception as e:
                import logging
                logging.error(f"删除文档 {document_id} 失败: {str(e)}")
                results[document_id] = False

        return results

    def get_kb_document_count(self, kb_id: str) -> int:
        """获取知识库文档数量"""
        return self.db.query(KBDocument).filter(KBDocument.kb_id == kb_id).count()

    def get_kb_chunk_count(self, kb_id: str) -> int:
        """获取知识库chunk数量"""
        return self.chunk_repo.get_kb_chunk_count(kb_id)