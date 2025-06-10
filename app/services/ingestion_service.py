from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
import json
import asyncio
from typing import List, Dict, Any, Optional
from pathlib import Path
import uuid
import time

from app.models.chunk import Chunk, IngestionJob
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.processors.processor_factory import ProcessorFactory
from app.utils.ai_utils import AIUtils
from app.utils.text_splitter import TextSplitter
from app.utils.task_queue import task_queue, TaskStatus
from app.repositories.document_repo import DocumentRepository
from app.repositories.milvus_repo import MilvusRepository
from app.services.kb_service import KBService
from app.db.database import SessionLocal

class IngestionService:
    """文档摄入服务 - v2版本（异步实现）"""

    def __init__(self, db: Session):
        self.db = db
        self.processor_factory = ProcessorFactory()
        self.ai_utils = AIUtils()
        self.text_splitter = TextSplitter()
        self.doc_repo = DocumentRepository(db)
        self.milvus_repo = MilvusRepository()
        self.kb_service = KBService(db)

    async def start_ingestion_job(self, kb_id: str, document_id: str, user_id: str) -> str:
        """启动文档摄入任务（v2版本：异步处理）"""
        # 创建任务记录
        job_id = str(uuid.uuid4())
        job = IngestionJob(
            id=job_id,
            kb_id=kb_id,
            document_id=document_id,
            status="pending"
        )
        self.db.add(job)
        self.db.commit()

        try:
            # 将任务添加到异步队列
            task_id = await task_queue.add_task(
                self._run_pipeline_sync,
                job_id, kb_id, document_id,
                timeout=30  # 30秒超时
            )

            # 更新job记录，关联task_id
            job.task_id = task_id
            self.db.commit()

            return job_id

        except Exception as e:
            # 如果添加任务失败，更新任务状态
            job.status = "failed"
            job.error_message = str(e)
            self.db.commit()
            raise e

    def _run_pipeline_sync(self, job_id: str, kb_id: str, document_id: str):
        """同步版本的流水线执行（在线程池中运行）"""
        # 创建新的数据库会话
        db = SessionLocal()
        try:
            # 更新任务状态
            job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
            if not job:
                raise Exception(f"任务不存在: {job_id}")

            job.status = "processing"
            db.commit()

            # 执行摄取流水线
            self._execute_pipeline(db, job_id, kb_id, document_id)

            # 更新任务状态为完成
            job.status = "completed"
            db.commit()

        except Exception as e:
            # 更新任务状态为失败
            job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = str(e)
                db.commit()
            raise e
        finally:
            db.close()

    def _execute_pipeline(self, db: Session, job_id: str, kb_id: str, document_id: str):
        """执行摄取流水线的核心逻辑"""
        # 1. 获取文档路径（预加载物理文件信息）
        document = db.query(Document).options(
            joinedload(Document.physical_file)
        ).filter(Document.id == document_id).first()

        if not document:
            raise Exception(f"文档不存在: {document_id}")

        if not document.physical_file:
            raise Exception(f"文档对应的物理文件不存在: {document_id}")

        # 2. 获取知识库的标签字典
        kb_service = KBService(db)
        kb = kb_service.get_kb_by_id(kb_id)
        if not kb:
            raise Exception(f"知识库不存在: {kb_id}")

        tag_directory = kb.tag_dictionary

        # 3. 确保Milvus Collection存在
        collection_name = self._ensure_milvus_collection(db, kb)

        # 4. 选择合适的处理器（使用物理文件路径）
        file_path = document.physical_file.file_path
        processor = self.processor_factory.get_processor(file_path)
        if not processor:
            raise Exception(f"不支持的文件类型: {file_path}")

        # 5. 提取文档内容
        markdown_text, image_paths = processor.extract_content(file_path)

        # 6. 处理图片描述
        if image_paths:
            markdown_text = self._process_images(markdown_text, image_paths)

        # 7. 分割文本
        chunk_texts = self.text_splitter.split_text(markdown_text)

        # 8. 处理每个chunk
        chunks = []
        milvus_data = []

        for i, chunk_text in enumerate(chunk_texts):
            try:
                # 生成标签
                tags = self.ai_utils.get_tags(chunk_text, tag_directory)

                # 确保tags是列表
                if not isinstance(tags, list):
                    print(f"警告: 标签生成返回非列表类型: {type(tags)}, 使用空列表")
                    tags = []

                # 生成嵌入向量
                embedding = self.ai_utils.get_embedding(chunk_text)

                # 创建chunk对象
                chunk_id = str(uuid.uuid4())
                chunk = Chunk(
                    id=chunk_id,
                    kb_id=kb_id,
                    document_id=document_id,
                    chunk_index=i,
                    content=chunk_text,
                    tags=json.dumps(tags, ensure_ascii=False)
                )
                chunks.append(chunk)

                # 准备Milvus数据
                milvus_data.append({
                    "chunk_id": chunk_id,
                    "document_id": document_id,
                    "tags": tags,
                    "embedding": embedding
                })

            except Exception as e:
                print(f"处理chunk {i} 时发生错误: {str(e)}, 跳过此chunk")
                continue

        # 9. 保存到SQLite
        db.add_all(chunks)
        db.commit()

        # 10. 保存到Milvus
        if milvus_data:
            self.milvus_repo.insert_chunks(kb_id, milvus_data)

        # 11. 更新KBDocument的最后摄取时间
        from app.models.document import KBDocument
        kb_document = db.query(KBDocument).filter(
            KBDocument.kb_id == kb_id,
            KBDocument.document_id == document_id
        ).first()

        if kb_document:
            kb_document.last_ingest_time = func.now()
            db.commit()

    def _process_images(self, markdown_text: str, image_paths: List[str]) -> str:
        """处理图片，获取描述并嵌入markdown"""
        for image_path in image_paths:
            try:
                # 获取图片描述
                description = self.ai_utils.get_image_description(image_path)

                # 替换占位符
                placeholder = f"[图片描述占位符: {image_path}]"
                if placeholder in markdown_text:
                    markdown_text = markdown_text.replace(
                        placeholder,
                        f"\n\n**图片描述**: {description}\n"
                    )
            except Exception as e:
                print(f"处理图片失败 {image_path}: {str(e)}")

        return markdown_text

    def get_job_status(self, job_id: str) -> Optional[IngestionJob]:
        """获取任务状态（结合队列状态）"""
        job = self.db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if not job:
            return None

        # 如果任务有task_id，检查队列中的状态
        if hasattr(job, 'task_id') and job.task_id:
            queue_task = task_queue.get_task_status(job.task_id)
            if queue_task:
                # 同步队列状态到数据库
                if queue_task.status == TaskStatus.RUNNING and job.status == "pending":
                    job.status = "processing"
                    self.db.commit()
                elif queue_task.status == TaskStatus.COMPLETED and job.status in ["pending", "processing"]:
                    job.status = "completed"
                    self.db.commit()
                elif queue_task.status in [TaskStatus.FAILED, TaskStatus.TIMEOUT] and job.status in ["pending", "processing"]:
                    job.status = "failed"
                    if queue_task.error:
                        job.error_message = queue_task.error
                    self.db.commit()

        return job

    def get_kb_jobs(self, kb_id: str) -> List[IngestionJob]:
        """获取知识库的所有摄入任务"""
        return self.db.query(IngestionJob).filter(
            IngestionJob.kb_id == kb_id
        ).order_by(IngestionJob.created_at.desc()).all()

    def get_queue_stats(self) -> Dict[str, Any]:
        """获取队列统计信息"""
        return task_queue.get_queue_stats()

    def _ensure_milvus_collection(self, db: Session, kb: KnowledgeBase) -> str:
        """确保知识库的Milvus Collection存在，返回collection名称"""
        # 如果已经有collection_id，先检查是否真的存在
        if kb.milvus_collection_id:
            collection_name = self.milvus_repo._normalize_collection_name(kb.id)
            # 检查collection是否真的存在
            if self.milvus_repo._collection_exists(kb.id):
                return kb.milvus_collection_id
            else:
                # collection不存在，需要重新创建
                print(f"警告: 知识库 {kb.id} 的collection {kb.milvus_collection_id} 不存在，将重新创建")

        # 创建新的collection
        collection_name = self.milvus_repo.create_collection(kb.id)

        # 更新知识库记录
        kb.milvus_collection_id = collection_name
        db.commit()

        return collection_name

    async def delete_document_index(self, kb_id: str, document_id: str):
        """删除文档的索引数据（从Milvus和SQLite中删除）"""
        try:
            # 1. 从Milvus中删除文档的所有chunks
            self.milvus_repo.delete_document_chunks(kb_id, document_id)

            # 2. 从SQLite中删除文档的所有chunks
            self.db.query(Chunk).filter(
                Chunk.kb_id == kb_id,
                Chunk.document_id == document_id
            ).delete()

            self.db.commit()

        except Exception as e:
            self.db.rollback()
            raise Exception(f"删除文档索引失败: {str(e)}")