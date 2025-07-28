from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func
from fastapi import UploadFile, HTTPException
from app.models.document import Document, KBDocument, PhysicalDocument
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User
from app.models.fragment import Fragment, KBFragment
from app.models.index import Index
from app.repositories.milvus_repo import MilvusRepository
from app.config import get_logger
from typing import List, Optional, Dict
import hashlib
import os
import uuid
import mimetypes
from pathlib import Path

class DocumentService:
    def __init__(self, db: Session):
        self.db = db
        # self.doc_repo = DocumentRepository(db)  # 暂时注释，直接使用db操作
        # self.chunk_repo = ChunkRepository(db)  # 摄入相关，暂时注释
        self.storage_path = Path("data/documents")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.milvus_repo = MilvusRepository()
        self.logger = get_logger(__name__)

    def _is_super_admin(self, user: User) -> bool:
        """检查用户是否为超级管理员"""
        return user.role == "system_admin"

    def _can_access_file_url(self, user: User) -> bool:
        """检查用户是否有权限查看文件URL（仅超级管理员）"""
        return self._is_super_admin(user)

    def _get_safe_file_url(self, physical_file, user: User) -> str:
        """根据用户权限返回安全的文件URL"""
        if not physical_file:
            return ""

        # 只有超级管理员才能看到真实的文件路径
        if self._can_access_file_url(user):
            return physical_file.url
        else:
            # 其他用户（包括普通管理员）都不能看到文件路径
            return ""

    def _calculate_file_hash(self, content: bytes) -> str:
        """计算文件内容的SHA256哈希值"""
        return hashlib.sha256(content).hexdigest()

    def _save_physical_file(self, content: bytes, content_hash: str, original_filename: str) -> str:
        """保存物理文件到存储路径，返回file:///协议的URL"""
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

        # 返回file:///协议的URL
        absolute_path = file_path.resolve()
        return f"file:///{absolute_path.as_posix()}"

    def upload_document(self, kb_id: str, user_id: str, uploaded_file: UploadFile) -> Document:
        """上传文档到知识库"""
        # 读取文件内容
        content = uploaded_file.file.read()
        uploaded_file.file.seek(0)  # 重置文件指针

        # 计算文件哈希
        content_hash = self._calculate_file_hash(content)

        try:
            # 检查物理文件是否已存在
            physical_file = self.db.query(PhysicalDocument).filter(
                PhysicalDocument.content_hash == content_hash
            ).first()

            if not physical_file:
                # 保存物理文件并获取file:///URL
                file_url = self._save_physical_file(content, content_hash, uploaded_file.filename)

                # 获取文件扩展名
                file_ext = Path(uploaded_file.filename).suffix

                # 获取MIME类型
                mime_type, _ = mimetypes.guess_type(uploaded_file.filename)
                if not mime_type:
                    mime_type = uploaded_file.content_type or "application/octet-stream"

                # 创建物理文件记录
                physical_file = PhysicalDocument(
                    content_hash=content_hash,
                    file_size=len(content),
                    mime_type=mime_type,
                    extension=file_ext,
                    url=file_url,
                    reference_count=0
                )
                self.db.add(physical_file)

            # 获取MIME类型（用于Document记录）
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
            if 'file_url' in locals() and not physical_file:
                # 从file:///URL提取本地路径并删除文件
                if file_url.startswith("file:///"):
                    local_path = file_url[8:]  # 移除file:///前缀
                    if os.path.exists(local_path):
                        os.remove(local_path)
            raise e

    def get_kb_documents(self, kb_id: str) -> List[KBDocument]:
        """获取知识库中的所有文档"""
        return self.db.query(KBDocument).filter(KBDocument.kb_id == kb_id).all()

    def get_kb_documents_with_chunk_count(self, kb_id: str, user: User) -> List[dict]:
        """获取知识库中的所有文档及其基本信息（暂时不包含chunk数量）"""
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
            # 暂时注释索引相关逻辑
            # is_index_outdated = False
            # if kb.last_tag_directory_update_time and kb_doc.last_ingest_time:
            #     is_index_outdated = kb.last_tag_directory_update_time > kb_doc.last_ingest_time
            # elif kb.last_tag_directory_update_time and not kb_doc.last_ingest_time:
            #     is_index_outdated = True

            # 暂时注释chunk相关逻辑
            # chunks = self.chunk_repo.get_chunks_by_document(kb_doc.document_id)

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
                    "file_url": self._get_safe_file_url(kb_doc.document.physical_file, user)
                },
                "chunk_count": 0,  # 暂时设为0，等摄入功能重构后再实现
                "uploader_username": kb_doc.document.uploader.username if kb_doc.document.uploader else None
            }
            # doc_dict["is_index_outdated"] = is_index_outdated  # 暂时注释
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
        """获取文档的文件路径（从file:///URL提取本地路径）"""
        # 使用joinedload预加载physical_file关系
        document = self.db.query(Document).options(
            joinedload(Document.physical_file)
        ).filter(Document.id == document_id).first()

        if document and document.physical_file:
            # 从file:///URL提取本地路径
            file_url = document.physical_file.url
            if file_url.startswith("file:///"):
                local_path = file_url[8:]  # 移除file:///前缀
                if os.path.exists(local_path):
                    return local_path
        return None

    def remove_document_from_kb(self, kb_id: str, document_id: str) -> bool:
        """
        从知识库中移除文档，执行完整的删除流程：
        1. 删除逻辑文档
        2. 删除逻辑文档对应的milvus索引
        3. 更新物理文档引用计数器，如果归零则删除物理文档
        4. 如果物理文档被删除，则进一步触发对fragment的清理
        """
        try:
            # 获取文档记录（预加载物理文件信息）
            document = self.db.query(Document).options(
                joinedload(Document.physical_file)
            ).filter(Document.id == document_id).first()

            if not document:
                self.logger.warning(f"文档不存在: {document_id}")
                return False

            # 获取知识库信息（用于Milvus操作）
            kb = self.db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
            if not kb:
                self.logger.warning(f"知识库不存在: {kb_id}")
                return False

            # 1. 删除Milvus中的文档索引
            try:
                self.logger.info(f"开始删除文档的Milvus索引: kb_id={kb_id}, document_id={document_id}")
                self.milvus_repo.delete_vectors_by_document(kb_id, document_id)
                self.logger.info(f"成功删除文档的Milvus索引: document_id={document_id}")
            except Exception as e:
                self.logger.error(f"删除Milvus索引失败: document_id={document_id}, 错误: {e}")
                # 继续执行，不因为Milvus删除失败而中断整个流程

            # 2. 删除知识库-文档关联
            kb_doc = self.db.query(KBDocument).filter(
                KBDocument.kb_id == kb_id,
                KBDocument.document_id == document_id
            ).first()

            if not kb_doc:
                self.logger.warning(f"知识库-文档关联不存在: kb_id={kb_id}, document_id={document_id}")
                return False

            self.db.delete(kb_doc)
            self.logger.info(f"删除知识库-文档关联: kb_id={kb_id}, document_id={document_id}")

            # 3. 检查文档是否还被其他知识库引用
            other_kb_refs = self.db.query(KBDocument).filter(
                KBDocument.document_id == document_id
            ).count()

            if other_kb_refs == 0:
                # 3.1 删除文档的所有Fragment相关数据
                self._delete_document_fragments(document_id)

                # 3.2 删除逻辑文档记录
                content_hash = document.content_hash
                self.db.delete(document)
                self.logger.info(f"删除逻辑文档: document_id={document_id}")

                # 3.3 更新物理文档引用计数
                physical_file = document.physical_file
                if physical_file:
                    physical_file.reference_count -= 1
                    self.logger.info(f"更新物理文档引用计数: content_hash={content_hash}, new_count={physical_file.reference_count}")

                    # 3.4 如果物理文档引用计数归零，删除物理文件
                    if physical_file.reference_count <= 0:
                        self._delete_physical_file(physical_file)
            else:
                self.logger.info(f"文档仍被其他知识库引用，不删除逻辑文档: document_id={document_id}, other_refs={other_kb_refs}")

            self.db.commit()
            self.logger.info(f"文档删除完成: kb_id={kb_id}, document_id={document_id}")
            return True

        except Exception as e:
            self.db.rollback()
            self.logger.error(f"删除文档失败: kb_id={kb_id}, document_id={document_id}, 错误: {e}")
            raise e

    def _delete_document_fragments(self, document_id: str) -> None:
        """删除文档的所有Fragment及其相关数据"""
        try:
            # 获取文档的所有Fragment
            fragments = self.db.query(Fragment).filter(
                Fragment.document_id == document_id
            ).all()

            if not fragments:
                self.logger.info(f"文档无Fragment需要删除: document_id={document_id}")
                return

            fragment_ids = [f.id for f in fragments]
            fragment_count = len(fragments)

            # 统计Fragment类型
            type_stats = {}
            for fragment in fragments:
                ftype = fragment.fragment_type
                type_stats[ftype] = type_stats.get(ftype, 0) + 1

            stats_str = ", ".join([f"{ftype}: {count}个" for ftype, count in type_stats.items()])
            self.logger.info(f"开始删除文档Fragment: document_id={document_id}, 共{fragment_count}个Fragment ({stats_str})")

            # 1. 删除Index条目（索引记录）
            index_deleted = self.db.query(Index).filter(
                Index.fragment_id.in_(fragment_ids)
            ).delete(synchronize_session=False)

            # 2. 删除KBFragment关联
            kb_fragment_deleted = self.db.query(KBFragment).filter(
                KBFragment.fragment_id.in_(fragment_ids)
            ).delete(synchronize_session=False)

            # 3. 删除Fragment记录
            fragment_deleted = self.db.query(Fragment).filter(
                Fragment.document_id == document_id
            ).delete(synchronize_session=False)

            self.logger.info(f"Fragment删除完成: document_id={document_id} - Fragment: {fragment_deleted}个, KB关联: {kb_fragment_deleted}个, 索引条目: {index_deleted}个")

        except Exception as e:
            self.logger.error(f"删除文档Fragment失败: document_id={document_id}, 错误: {e}")
            raise e

    def _delete_physical_file(self, physical_file: PhysicalDocument):
        try:
            content_hash = physical_file.content_hash
            file_url = physical_file.url

            # 删除物理文件
            if file_url.startswith("file:///"):
                local_path = file_url[8:]  # 移除file:///前缀
                if os.path.exists(local_path):
                    os.remove(local_path)
                    self.logger.info(f"删除物理文件: {local_path}")
                else:
                    self.logger.warning(f"物理文件不存在: {local_path}")

            # 删除物理文件记录
            self.db.delete(physical_file)
            self.logger.info(f"删除物理文件记录: content_hash={content_hash}")

        except Exception as e:
            self.logger.error(f"删除物理文件失败: content_hash={physical_file.content_hash}, 错误: {e}")
            raise

    def batch_remove_documents(self, kb_id: str, document_ids: List[str]) -> Dict[str, bool]:
        results = {}
        try:
            for document_id in document_ids:
                try:
                    success = self.remove_document_from_kb(kb_id, document_id)
                    results[document_id] = success
                except Exception as e:
                    self.logger.error(f"删除文档 {document_id} 失败: {str(e)}")
                    results[document_id] = False

            return results
        except Exception as e:
            self.logger.error(f"批量删除文档失败: {str(e)}")
            return results

    def get_kb_document_count(self, kb_id: str) -> int:
        """获取知识库文档数量"""
        return self.db.query(KBDocument).filter(KBDocument.kb_id == kb_id).count()

    def get_kb_chunk_count(self, kb_id: str) -> int:
        """获取知识库Fragment数量（文档块数）"""
        from app.models.fragment import Fragment, KBFragment
        return self.db.query(Fragment).join(
            KBFragment, Fragment.id == KBFragment.fragment_id
        ).filter(KBFragment.kb_id == kb_id).count()