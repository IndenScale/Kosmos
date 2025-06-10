from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
import json
import asyncio
from typing import List, Dict, Any, Optional
from pathlib import Path
import uuid

from app.models.chunk import Chunk, IngestionJob
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.processors.processor_factory import ProcessorFactory
from app.utils.ai_utils import AIUtils
from app.utils.text_splitter import TextSplitter
from app.repositories.document_repo import DocumentRepository
from app.repositories.milvus_repo import MilvusRepository
from app.services.kb_service import KBService

class IngestionService:
    """文档摄入服务 - v1版本（同步实现）"""

    def __init__(self, db: Session):
        self.db = db
        self.processor_factory = ProcessorFactory()
        self.ai_utils = AIUtils()
        self.text_splitter = TextSplitter()
        self.doc_repo = DocumentRepository(db)
        self.milvus_repo = MilvusRepository()
        self.kb_service = KBService(db)

    def start_ingestion_job(self, kb_id: str, document_id: str, user_id: str) -> str:
        """启动文档摄入任务（v1版本：同步处理）"""
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
            # 同步执行摄入流水线
            self._run_pipeline(job_id, kb_id, document_id)
            return job_id
        except Exception as e:
            # 如果出错，更新任务状态
            job.status = "failed"
            job.error_message = str(e)
            self.db.commit()
            raise e

    def _run_pipeline(self, job_id: str, kb_id: str, document_id: str):

        job = self.db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        job.status = "processing"
        self.db.commit()
        """执行摄取流水线"""
        kb_id = job.kb_id
        document_id = job.document_id

        try:
            # 1. 获取文档路径（预加载物理文件信息）
            document = self.db.query(Document).options(
                joinedload(Document.physical_file)
            ).filter(Document.id == document_id).first()

            if not document:
                raise Exception(f"文档不存在: {document_id}")

            if not document.physical_file:
                raise Exception(f"文档对应的物理文件不存在: {document_id}")

            # 2. 获取知识库的标签字典
            kb = self.kb_service.get_kb_by_id(kb_id)
            if not kb:
                raise Exception(f"知识库不存在: {kb_id}")

            tag_directory = kb.tag_dictionary

            # 3. 确保Milvus Collection存在
            collection_name = self._ensure_milvus_collection(kb)

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
            self.db.add_all(chunks)
            self.db.commit()

            # 10. 保存到Milvus
            if milvus_data:
                self.milvus_repo.insert_chunks(kb_id, milvus_data)

            # 11. 更新KBDocument的最后摄取时间
            from app.models.document import KBDocument
            kb_document = self.db.query(KBDocument).filter(
                KBDocument.kb_id == kb_id,
                KBDocument.document_id == document_id
            ).first()

            if kb_document:
                kb_document.last_ingest_time = func.now()
                self.db.commit()

            # 12. 更新任务状态
            job.status = "completed"
            self.db.commit()

        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)
            self.db.commit()
            raise e

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
        """获取任务状态"""
        return self.db.query(IngestionJob).filter(IngestionJob.id == job_id).first()

    def get_kb_jobs(self, kb_id: str) -> List[IngestionJob]:
        """获取知识库的所有摄入任务"""
        return self.db.query(IngestionJob).filter(IngestionJob.kb_id == kb_id).order_by(IngestionJob.created_at.desc()).all()

    def _ensure_milvus_collection(self, kb: KnowledgeBase) -> str:
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
        self.db.commit()

        return collection_name