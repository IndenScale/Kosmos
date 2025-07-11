from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
import json
import asyncio
import logging
import os
from typing import List, Dict, Any, Optional
from pathlib import Path
import uuid
import time
import hashlib
import numpy as np

from app.models.chunk import Chunk, IngestionJob
from app.models.document import Document, KBDocument
from app.models.knowledge_base import KnowledgeBase
from app.models.page_screenshot import PageScreenshot
from app.processors.processor_factory import ProcessorFactory
from app.utils.ai_utils import AIUtils
from app.utils.intelligent_text_splitter import IntelligentTextSplitter
from app.utils.task_queue import task_queue, TaskStatus
from app.repositories.document_repo import DocumentRepository
from app.repositories.milvus_repo import MilvusRepository
from app.services.kb_service import KBService
from app.services.screenshot_service import ScreenshotService
from app.db.database import SessionLocal

# 配置日志
logger = logging.getLogger(__name__)

class IngestionService:
    """文档摄入服务 - v2版本（异步实现）
    
    重构后的摄入流程：
    1. 异构文档 → PDF转换 → 逐页截图 → Markdown+图片 → 图像理解 → 完整Markdown
    2. Chunking（文本分割）
    3. [可选] Tagging（标签生成）- 可以跳过，由SDTM或TaggingService后续处理
    4. Embedding（嵌入向量生成）
    5. Storing（存储到SQLite和Milvus）
    
    新的架构分离：
    - IngestionService：负责格式转换、分块、嵌入、存储
    - TaggingService：负责传统的标签生成（可选）
    - SDTM：负责智能标签生成和标签字典优化（替代TaggingService）
    """

    def __init__(self, db: Session):
        self.db = db
        self.processor_factory = ProcessorFactory()
        self.ai_utils = AIUtils()
        self.intelligent_splitter = IntelligentTextSplitter()
        self.doc_repo = DocumentRepository(db)
        self.milvus_repo = MilvusRepository()
        self.kb_service = KBService(db)

    def _calculate_content_hash(self, content: str) -> str:
        """计算内容的哈希值用于去重"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def _check_document_duplicate(self, kb_id: str, filename: str, content_hash: str) -> Optional[Document]:
        """检查文档是否已存在（基于文件名和内容哈希）"""
        return self.db.query(Document).join(KBDocument).filter(
            KBDocument.kb_id == kb_id,
            Document.filename == filename,
            Document.content_hash == content_hash
        ).first()

    def _deduplicate_chunks(self, chunks: List[str], similarity_threshold: float = 0.95) -> List[str]:
        """对chunks进行去重，移除高度相似的内容"""
        if len(chunks) <= 1:
            return chunks
        
        logger.info(f"开始chunk去重，原始数量: {len(chunks)}")
        
        deduplicated = []
        seen_hashes = set()
        
        for i, chunk in enumerate(chunks):
            # 跳过过短的内容
            if len(chunk.strip()) < 50:
                deduplicated.append(chunk)
                continue
            
            # 计算内容哈希进行精确去重
            content_hash = self._calculate_content_hash(chunk.strip())
            if content_hash in seen_hashes:
                logger.debug(f"跳过重复chunk {i}: {chunk[:50]}...")
                continue
            
            # 检查与已有chunks的相似度
            is_duplicate = False
            for existing_chunk in deduplicated:
                if len(existing_chunk.strip()) < 50:
                    continue
                
                similarity = self._calculate_text_similarity(chunk, existing_chunk)
                if similarity > similarity_threshold:
                    logger.debug(f"跳过相似chunk {i} (相似度: {similarity:.3f}): {chunk[:50]}...")
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                deduplicated.append(chunk)
                seen_hashes.add(content_hash)
        
        logger.info(f"chunk去重完成，去重后数量: {len(deduplicated)}")
        return deduplicated

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """计算两个文本的相似度（基于字符集合的Jaccard相似度）"""
        try:
            # 清理文本
            text1_clean = text1.strip().lower()
            text2_clean = text2.strip().lower()
            
            if not text1_clean or not text2_clean:
                return 0.0
            
            # 使用字符级别的n-gram计算相似度
            def get_ngrams(text, n=3):
                return set(text[i:i+n] for i in range(len(text) - n + 1))
            
            ngrams1 = get_ngrams(text1_clean)
            ngrams2 = get_ngrams(text2_clean)
            
            if not ngrams1 or not ngrams2:
                return 0.0
            
            intersection = len(ngrams1.intersection(ngrams2))
            union = len(ngrams1.union(ngrams2))
            
            return intersection / union if union > 0 else 0.0
            
        except Exception as e:
            logger.warning(f"计算文本相似度失败: {e}")
            return 0.0

    async def start_ingestion_job(self, kb_id: str, document_id: str, user_id: str, 
                                  skip_tagging: bool = False, force_reindex: bool = False) -> str:
        """启动文档摄入任务（v2版本：异步处理）
        
        Args:
            kb_id: 知识库ID
            document_id: 文档ID
            user_id: 用户ID
            skip_tagging: 是否跳过标签生成步骤（默认False）
            force_reindex: 是否强制重新索引（默认False）
        """
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
            # 确保任务队列已启动
            if not task_queue._running:
                logger.warning("任务队列未运行，尝试启动...")
                await task_queue.start()
            
            logger.debug(f"任务队列状态: running={task_queue._running}, worker_task={task_queue._worker_task}")
            
            # 将任务添加到异步队列
            task_id = await task_queue.add_task(
                self._run_pipeline_sync,
                job_id, kb_id, document_id, skip_tagging, force_reindex,
                timeout=300  # 5分钟超时
            )

            # 更新job记录，关联task_id
            job.task_id = task_id  # type: ignore
            self.db.commit()

            return job_id

        except Exception as e:
            # 如果添加任务失败，更新任务状态
            job.status = "failed"  # type: ignore
            job.error_message = str(e)  # type: ignore
            self.db.commit()
            raise e

    def _run_pipeline_sync(self, job_id: str, kb_id: str, document_id: str, skip_tagging: bool = False, force_reindex: bool = False):
        """同步版本的流水线执行（在线程池中运行）"""
        # 创建新的数据库会话
        db = SessionLocal()
        try:
            logger.info(f"开始处理任务 {job_id}")
            # 更新任务状态
            job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
            if not job:
                raise Exception(f"任务不存在: {job_id}")

            job.status = "processing"  # type: ignore
            db.commit()
            logger.info(f"任务状态更新为 processing: {job_id}")

            # 执行摄取流水线
            self._execute_pipeline(db, job_id, kb_id, document_id, skip_tagging, force_reindex)

            # 更新任务状态为完成
            job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
            if job:
                job.status = "completed"  # type: ignore
                db.commit()
                logger.info(f"任务完成: {job_id}")

        except Exception as e:
            logger.error(f"任务执行失败: {job_id}, 错误: {str(e)}")
            # 更新任务状态为失败
            db.rollback()  # 回滚事务
            job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
            if job:
                job.status = "failed"  # type: ignore
                job.error_message = str(e)  # type: ignore
                db.commit()
            raise e
        finally:
            db.close()

    def _execute_pipeline(self, db: Session, job_id: str, kb_id: str, document_id: str, skip_tagging: bool = False, force_reindex: bool = False):
        """执行摄取流水线的核心逻辑
        
        Args:
            skip_tagging: 是否跳过标签生成步骤，如果为True，则chunks将以空标签存储
            force_reindex: 是否强制重新索引，如果为True，则跳过重复检查
        """
        logger.info(f"开始执行摄取流水线: job_id={job_id}, document_id={document_id}, skip_tagging={skip_tagging}, force_reindex={force_reindex}")
        
        # 1. 获取文档路径（预加载物理文件信息）
        document = db.query(Document).options(
            joinedload(Document.physical_file)
        ).filter(Document.id == document_id).first()

        if not document:
            raise Exception(f"文档不存在: {document_id}")

        if not document.physical_file:
            raise Exception(f"文档对应的物理文件不存在: {document_id}")

        logger.info(f"文档信息获取成功: {document.filename}")

        # 2. 检查是否已存在该文档的索引（除非强制重新索引）
        if not force_reindex:
            existing_chunks = db.query(Chunk).filter(
                Chunk.kb_id == kb_id,
                Chunk.document_id == document_id
            ).first()
            
            if existing_chunks:
                logger.warning(f"文档 {document_id} 已存在索引，跳过重复摄入。如需重新索引，请设置 force_reindex=True")
                return

        # 3. 获取知识库的标签字典（即使跳过标签生成也要获取，以备后用）
        kb_service = KBService(db)
        kb = kb_service.get_kb_by_id(kb_id)
        if not kb:
            raise Exception(f"知识库不存在: {kb_id}")

        tag_directory = kb.tag_dictionary if not skip_tagging else None
        logger.info(f"知识库信息获取成功: {kb.name}, 标签字典: {'存在' if tag_directory is not None else '不存在/跳过'}")

        # 4. 确保Milvus Collection存在
        collection_name = self._ensure_milvus_collection(db, kb)
        logger.info(f"Milvus Collection 准备完成: {collection_name}")

        # 5. 选择合适的处理器（使用物理文件路径）
        file_path = document.physical_file.file_path
        
        # 处理跨平台路径问题：标准化路径格式
        file_path = os.path.normpath(file_path)
        
        # 确保使用绝对路径
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)
        
        # 验证文件是否存在
        if not os.path.exists(file_path):
            raise Exception(f"文件不存在: {file_path}")
        
        processor = self.processor_factory.get_processor(file_path)
        if not processor:
            raise Exception(f"不支持的文件类型: {file_path}")

        # 6. 提取文档内容（现在返回结构化块）
        content_blocks, screenshot_paths = processor.extract_content(file_path)
        
        # 7. 处理页面截图
        screenshot_service = ScreenshotService(db)
        page_screenshots = []
        screenshot_id_mapping = {}
        
        # 检查处理器是否需要截图
        if processor.needs_screenshot(file_path):
            logger.info(f"处理器 {processor.__class__.__name__} 需要截图，开始处理截图")
            
            # 首先检查是否已存在该文档的截图记录
            existing_screenshots = screenshot_service.get_screenshots_by_document(document_id)
            if existing_screenshots and not force_reindex:
                logger.info(f"发现现有截图记录: {document_id}, 共{len(existing_screenshots)}个，重用现有记录")
                page_screenshots = existing_screenshots
                screenshot_id_mapping = {ss.page_number: ss.id for ss in existing_screenshots}
                logger.debug(f"重用页码到截图ID映射: {screenshot_id_mapping}")
            elif screenshot_paths:
                logger.info(f"开始处理 {len(screenshot_paths)} 个截图路径")
                # 为每个截图路径创建PageScreenshot记录
                for i, screenshot_path in enumerate(screenshot_paths):
                    try:
                        screenshot_id = str(uuid.uuid4())
                        screenshot = PageScreenshot(
                            id=screenshot_id,
                            document_id=document_id,
                            page_number=i + 1,  # 页码从1开始
                            file_path=screenshot_path
                        )
                        page_screenshots.append(screenshot)
                        logger.debug(f"创建页面截图记录: 第{i + 1}页 -> {screenshot_path}, ID: {screenshot_id}")
                    except Exception as e:
                        logger.error(f"创建页面截图记录失败: 第{i + 1}页, 错误: {str(e)}")
                
                # 批量保存页面截图记录
                if page_screenshots:
                    db.add_all(page_screenshots)
                    db.commit()
                    screenshot_id_mapping = {ss.page_number: ss.id for ss in page_screenshots}
                    logger.info(f"保存了{len(page_screenshots)}个页面截图记录")
                    logger.debug(f"页码到截图ID映射: {screenshot_id_mapping}")
                else:
                    logger.info("没有页面截图需要保存")
            else:
                logger.warning("处理器需要截图但未返回截图路径")
        else:
            logger.info(f"处理器 {processor.__class__.__name__} 不需要截图，跳过截图处理")

        # 10. 使用智能分割器将块转换为chunks
        logger.debug(f"开始使用智能分割器处理内容")
        
        # 确保 content_blocks 是 IntelligentTextSplitter 期望的列表格式
        if isinstance(content_blocks, str):
            # 如果是字符串（来自Generic/Code处理器），包装成结构化块
            content_blocks_structured = [{'type': 'text', 'content': content_blocks}]
        elif isinstance(content_blocks, list):
            # 如果已经是列表（来自Json处理器），直接使用
            content_blocks_structured = content_blocks
        else:
            # 处理未知类型，记录错误并继续
            logger.warning(f"未知的 content_blocks 类型: {type(content_blocks)}，将尝试转换为空列表")
            content_blocks_structured = []

        chunks = self.intelligent_splitter.split(content_blocks_structured)
        logger.info(f"智能分割后的chunks数量: {len(chunks)}")

        # 11. 对chunks进行去重
        chunks = self._deduplicate_chunks(chunks)

        # 12. 为每个chunk生成标签、嵌入向量并建立截图关联
        chunk_records = []
        milvus_data = []

        for i, chunk_text in enumerate(chunks):
            chunk_id = str(uuid.uuid4())
            
            # 打印正在处理的chunk信息
            logger.debug(f"\n处理 Chunk {i}:")
            logger.debug(f"Chunk内容长度: {len(chunk_text)} 字符")
            logger.debug(f"Chunk内容预览: {chunk_text[:100]}...")

            # 12.1. 根据配置决定是否生成标签
            tags = []
            if skip_tagging:
                logger.debug("跳过标签生成步骤")
            else:
                # 使用知识库的标签字典生成标签
                # 确保 tag_directory 是一个字典
                tag_dict = tag_directory if isinstance(tag_directory, dict) else {}
                tags = self.ai_utils.get_tags(chunk_text, tag_dict)
                logger.debug(f"生成标签: {tags}")

            # 12.2. 生成嵌入向量
            embedding = self.ai_utils.get_embedding(chunk_text)
            logger.debug(f"生成嵌入向量，维度: {len(embedding)}")
            
            screenshot_ids = self._associate_chunks_with_screenshots([chunk_text], screenshot_id_mapping, len(page_screenshots))[0]
            logger.debug(f"关联的截图IDs: {screenshot_ids}")

            # 12.3. 创建Chunk记录
            chunk = Chunk(
                id=chunk_id,
                kb_id=kb_id,
                document_id=document_id,
                chunk_index=i,
                content=chunk_text,
                tags=json.dumps(tags, ensure_ascii=False),
                page_screenshot_ids=json.dumps(screenshot_ids, ensure_ascii=False) if screenshot_ids else None
            )
            chunk_records.append(chunk)
            logger.debug(f"创建chunk对象，截图IDs字段: {chunk.page_screenshot_ids}")

            # 12.4. 准备Milvus数据
            milvus_data.append({
                "chunk_id": chunk_id,
                "document_id": document_id,
                "tags": tags,
                "embedding": embedding
            })

        # 13. 批量保存chunks到SQLite
        logger.info(f"\n批量保存 {len(chunk_records)} 个chunks到数据库")
        db.add_all(chunk_records)
        db.commit()

        # 14. 批量保存chunks到Milvus
        logger.info(f"准备保存 {len(milvus_data)} 个chunks到Milvus")
        try:
            self.milvus_repo.insert_chunks(collection_name, milvus_data)
            logger.info(f"成功保存 {len(milvus_data)} 个chunks到Milvus")
        except Exception as e:
            logger.error(f"保存到Milvus失败: {str(e)}")
            # 注意：不要因为Milvus失败而回滚SQLite，数据一致性由业务逻辑保证

        # 15. 更新文档的最后摄入时间
        kb_document = db.query(KBDocument).filter(
            KBDocument.kb_id == kb_id,
            KBDocument.document_id == document_id
        ).first()
        
        if kb_document:
            kb_document.last_ingest_time = func.now()  # type: ignore
            db.commit()
            logger.info(f"已更新文档的最后摄入时间: {document_id}")
        else:
            logger.warning(f"未找到对应的KBDocument记录: kb_id={kb_id}, document_id={document_id}")

        logger.info(f"摄取任务完成: {file_path}")
        
        if skip_tagging:
            logger.info(f"摄入完成 - 跳过标签生成：{len(chunk_records)} 个chunks已存储，等待后续标注")
        else:
            logger.info(f"摄入完成 - 包含标签生成：{len(chunk_records)} 个chunks已存储并标注")

    def get_job_status(self, job_id: str) -> Optional[IngestionJob]:
        """获取任务状态（结合队列状态）"""
        job = self.db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if not job:
            return None

        # 如果任务有task_id，检查队列中的状态
        if hasattr(job, 'task_id') and job.task_id is not None:
            queue_task = task_queue.get_task_status(str(job.task_id))
            if queue_task:
                # 同步队列状态到数据库
                if queue_task.status == TaskStatus.RUNNING and job.status == "pending":  # type: ignore
                    job.status = "processing"  # type: ignore
                    self.db.commit()
                elif queue_task.status == TaskStatus.COMPLETED and job.status in ["pending", "processing"]: # type: ignore
                    job.status = "completed"  # type: ignore
                    self.db.commit()
                elif queue_task.status in [TaskStatus.FAILED, TaskStatus.TIMEOUT] and job.status in ["pending", "processing"]: # type: ignore
                    job.status = "failed"  # type: ignore
                    if queue_task.error:
                        job.error_message = queue_task.error  # type: ignore
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
    
    def get_ingestion_stats(self, kb_id: str) -> Dict[str, Any]:
        """获取摄入统计信息"""
        try:
            from app.repositories.chunk_repo import ChunkRepository
            
            chunk_repo = ChunkRepository(self.db)
            
            # 获取基本统计
            total_chunks = chunk_repo.get_kb_chunk_count(kb_id)
            untagged_chunks = chunk_repo.get_untagged_chunks(kb_id)
            untagged_count = len(untagged_chunks)
            tagged_count = total_chunks - untagged_count
            
            return {
                "total_chunks": total_chunks,
                "tagged_chunks": tagged_count,
                "untagged_chunks": untagged_count,
                "tagging_completion_rate": (tagged_count / total_chunks * 100) if total_chunks > 0 else 0,
                "ready_for_sdtm": untagged_count > 0,  # 是否适合使用SDTM
                "ready_for_tagging_service": untagged_count > 0  # 是否适合使用TaggingService
            }
            
        except Exception as e:
            return {
                "total_chunks": 0,
                "tagged_chunks": 0,
                "untagged_chunks": 0,
                "tagging_completion_rate": 0,
                "ready_for_sdtm": False,
                "ready_for_tagging_service": False,
                "error": str(e)
            }

    def _ensure_milvus_collection(self, db: Session, kb: KnowledgeBase) -> str:
        """确保知识库的Milvus Collection存在，返回collection名称"""
        # 获取标准化的集合名称
        collection_name = self.milvus_repo._normalize_collection_name(str(kb.id))
        
        # 检查collection是否存在
        if self.milvus_repo._collection_exists(str(kb.id)):
            # 如果集合存在，但数据库中的记录不匹配，更新数据库记录
            if kb.milvus_collection_id != collection_name: # type: ignore
                logger.info(f"更新知识库 {kb.id} 的collection名称: {kb.milvus_collection_id} -> {collection_name}")
                kb.milvus_collection_id = collection_name # type: ignore
                db.commit()
            return collection_name
        else:
            # collection不存在，需要创建
            if kb.milvus_collection_id is not None:
                logger.warning(f"警告: 知识库 {kb.id} 的collection {kb.milvus_collection_id} 不存在，将重新创建为 {collection_name}")
            else:
                logger.info(f"为知识库 {kb.id} 创建新的collection: {collection_name}")

        # 创建新的collection
        collection_name = self.milvus_repo.create_collection(str(kb.id))

        # 更新知识库记录
        kb.milvus_collection_id = collection_name # type: ignore
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
    
    def _extract_page_numbers_from_chunk(self, chunk_content: str) -> List[int]:
        """从chunk内容中提取页码信息
        
        Args:
            chunk_content: chunk文本内容
            
        Returns:
            List[int]: 页码列表
        """
        import re
        
        page_numbers = []
        
        # 方式1: 查找markdown标题中的页码 "## 第X页"
        title_pattern = r'##\s*第(\d+)页'
        title_matches = re.findall(title_pattern, chunk_content)
        for match in title_matches:
            try:
                page_num = int(match)
                if page_num not in page_numbers:
                    page_numbers.append(page_num)
            except ValueError:
                continue
        
        # 方式2: 查找文本中的页码标记 "第X页"（不限于标题）
        text_pattern = r'第(\d+)页'
        text_matches = re.findall(text_pattern, chunk_content)
        for match in text_matches:
            try:
                page_num = int(match)
                if page_num not in page_numbers:
                    page_numbers.append(page_num)
            except ValueError:
                continue
        
        # 方式3: 如果没有找到明确的页码标记，尝试推断
        if not page_numbers:
            # 检查是否包含文档开头的特征（通常是第1页）
            if any(keyword in chunk_content.lower() for keyword in ['摘要', 'abstract', '目录', 'contents', '前言']):
                page_numbers.append(1)
            # 检查是否包含结尾特征（假设是最后一页，但这个逻辑可能不准确）
            elif any(keyword in chunk_content.lower() for keyword in ['参考文献', 'references', '附录', 'appendix']):
                # 这里暂时不做假设，因为无法确定具体页码
                pass
        
        # 如果仍然没有页码，但chunk内容很短，可能是跨页的内容
        # 这种情况下我们先不关联任何页面，避免错误关联
        
        return sorted(page_numbers)

    def _associate_chunks_with_screenshots(self, chunks: List[str], screenshot_id_mapping: dict, total_pages: int) -> List[List[str]]:
        """智能关联chunks与截图IDs
        
        Args:
            chunks: 文本chunks列表
            screenshot_id_mapping: 页码到截图ID的映射 {page_num: screenshot_id}
            total_pages: 总页数
            
        Returns:
            List[List[str]]: 每个chunk对应的截图IDs列表
        """
        chunk_screenshot_associations = []
        
        if not screenshot_id_mapping or total_pages == 0:
            # 如果没有截图，所有chunk返回空列表
            return [[] for _ in chunks]
        
        logger.info(f"开始智能关联 {len(chunks)} 个chunks 与 {total_pages} 页截图")
        
        # 方法1: 先尝试从chunk内容中提取明确的页码标记
        explicit_page_mappings = []
        for i, chunk in enumerate(chunks):
            page_numbers = self._extract_page_numbers_from_chunk(chunk)
            explicit_page_mappings.append(page_numbers)
            if page_numbers:
                logger.debug(f"Chunk {i}: 明确提取到页码 {page_numbers}")
            else:
                logger.debug(f"Chunk {i}: 未找到明确页码标记")
        
        # 方法2: 如果大部分chunk都没有明确页码，使用智能推断
        chunks_with_explicit_pages = [i for i, pages in enumerate(explicit_page_mappings) if pages]
        
        if len(chunks_with_explicit_pages) < len(chunks) * 0.3:  # 少于30%的chunk有明确页码
            logger.info("使用基于顺序的智能页码推断算法")
            chunk_screenshot_associations = self._infer_page_associations_by_order(
                chunks, screenshot_id_mapping, total_pages
            )
        else:
            logger.info("使用基于明确页码标记的关联算法")
            chunk_screenshot_associations = self._associate_by_explicit_pages(
                explicit_page_mappings, screenshot_id_mapping
            )
        
        return chunk_screenshot_associations
    
    def _infer_page_associations_by_order(self, chunks: List[str], screenshot_id_mapping: dict, total_pages: int) -> List[List[str]]:
        """基于chunk顺序推断页码关联
        
        策略：
        1. 假设chunks按文档顺序排列
        2. 平均分配chunk到页面
        3. 为每个chunk提供相邻页面的上下文（扩展1-2页）
        """
        chunk_associations = []
        
        if len(chunks) == 0:
            return []
        
        # 计算每个chunk平均覆盖的页面范围
        pages_per_chunk = total_pages / len(chunks)
        
        for i, chunk in enumerate(chunks):
            # 计算当前chunk的中心页码
            center_page = int((i + 0.5) * pages_per_chunk) + 1
            center_page = max(1, min(center_page, total_pages))
            
            # 扩展上下文：当前页 ± 1页（确保用户能看到上下文）
            start_page = max(1, center_page - 1)
            end_page = min(total_pages, center_page + 1)
            
            # 收集这个范围内的所有截图ID
            chunk_screenshot_ids = []
            for page_num in range(start_page, end_page + 1):
                if page_num in screenshot_id_mapping:
                    chunk_screenshot_ids.append(screenshot_id_mapping[page_num])
            
            chunk_associations.append(chunk_screenshot_ids)
            
            logger.debug(f"Chunk {i}: 推断页码范围 {start_page}-{end_page}, 关联截图IDs {chunk_screenshot_ids}")
        
        return chunk_associations
    
    def _associate_by_explicit_pages(self, explicit_page_mappings: List[List[int]], screenshot_id_mapping: dict) -> List[List[str]]:
        """基于明确的页码标记进行关联，并为无页码的chunk继承上一个chunk的页码"""
        chunk_associations = []
        last_known_pages = []  # 记录最后已知的页码
        
        for i, page_numbers in enumerate(explicit_page_mappings):
            chunk_screenshot_ids = []
            
            if page_numbers:
                # 有明确页码，更新最后已知页码
                last_known_pages = page_numbers
                
                # 为明确的页码添加上下文页面
                all_pages = set(page_numbers)
                for page_num in page_numbers:
                    # 添加相邻页面作为上下文
                    all_pages.add(max(1, page_num - 1))
                    all_pages.add(page_num + 1)
                
                # 转换为截图IDs
                for page_num in sorted(all_pages):
                    if page_num in screenshot_id_mapping:
                        chunk_screenshot_ids.append(screenshot_id_mapping[page_num])
                
                logger.debug(f"Chunk {i}: 基于明确页码 {page_numbers} 关联截图IDs {chunk_screenshot_ids}")
                
            else:
                # 没有明确页码，继承上一个已知页码
                if last_known_pages:
                    # 使用最后已知的页码，但稍微扩展范围以包含可能的后续页面
                    inherited_pages = set(last_known_pages)
                    
                    # 为继承的页码扩展范围（当前页 ± 1，以及可能的后续页面）
                    max_known_page = max(last_known_pages)
                    for page_num in last_known_pages:
                        inherited_pages.add(max(1, page_num - 1))
                        inherited_pages.add(page_num + 1)
                    
                    # 还要考虑可能跨页的情况，添加后续页面
                    inherited_pages.add(max_known_page + 1)
                    inherited_pages.add(max_known_page + 2)
                    
                    # 转换为截图IDs
                    for page_num in sorted(inherited_pages):
                        if page_num in screenshot_id_mapping:
                            chunk_screenshot_ids.append(screenshot_id_mapping[page_num])
                    
                    logger.debug(f"Chunk {i}: 继承页码 {sorted(last_known_pages)} (+扩展) 关联截图IDs {chunk_screenshot_ids}")
                else:
                    logger.debug(f"Chunk {i}: 无明确页码且无可继承页码，截图IDs为空")
            
            chunk_associations.append(chunk_screenshot_ids)
        
        return chunk_associations

    async def cleanup_duplicate_chunks(self, kb_id: str, similarity_threshold: float = 0.95) -> Dict[str, Any]:
        """清理知识库中的重复chunks
        
        Args:
            kb_id: 知识库ID
            similarity_threshold: 相似度阈值，超过此值的chunks将被视为重复
            
        Returns:
            Dict包含清理统计信息
        """
        logger.info(f"开始清理知识库 {kb_id} 中的重复chunks，相似度阈值: {similarity_threshold}")
        
        try:
            # 获取所有chunks
            chunks = self.db.query(Chunk).filter(Chunk.kb_id == kb_id).order_by(Chunk.created_at).all()
            
            if len(chunks) <= 1:
                return {
                    "total_chunks": len(chunks),
                    "duplicates_removed": 0,
                    "remaining_chunks": len(chunks),
                    "message": "chunks数量不足，无需去重"
                }
            
            logger.info(f"找到 {len(chunks)} 个chunks，开始去重分析")
            
            chunks_to_remove = []
            seen_hashes = set()
            
            for i, chunk in enumerate(chunks):
                content = chunk.content.strip()
                
                # 跳过过短的内容
                if len(content) < 50:
                    continue
                
                # 计算内容哈希进行精确去重
                content_hash = self._calculate_content_hash(content)
                if content_hash in seen_hashes:
                    logger.debug(f"发现重复chunk (哈希匹配): {chunk.id}")
                    chunks_to_remove.append(chunk)
                    continue
                
                # 检查与已保留chunks的相似度
                is_duplicate = False
                for j in range(i):
                    if chunks[j] in chunks_to_remove:
                        continue
                    
                    existing_content = chunks[j].content.strip()
                    if len(existing_content) < 50:
                        continue
                    
                    similarity = self._calculate_text_similarity(content, existing_content)
                    if similarity > similarity_threshold:
                        logger.debug(f"发现相似chunk (相似度: {similarity:.3f}): {chunk.id} vs {chunks[j].id}")
                        chunks_to_remove.append(chunk)
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    seen_hashes.add(content_hash)
            
            # 删除重复的chunks
            removed_count = 0
            if chunks_to_remove:
                logger.info(f"准备删除 {len(chunks_to_remove)} 个重复chunks")
                
                # 从Milvus中删除
                kb = self.kb_service.get_kb_by_id(kb_id)
                if kb and kb.milvus_collection_id is not None:
                    chunk_ids_to_remove = [chunk.id for chunk in chunks_to_remove]
                    try:
                        self.milvus_repo.delete_chunks_by_ids(str(kb.milvus_collection_id), chunk_ids_to_remove)
                        logger.info(f"从Milvus中删除了 {len(chunk_ids_to_remove)} 个chunks")
                    except Exception as e:
                        logger.error(f"从Milvus删除chunks失败: {e}")
                
                # 从SQLite中删除
                for chunk in chunks_to_remove:
                    self.db.delete(chunk)
                    removed_count += 1
                
                self.db.commit()
                logger.info(f"成功删除 {removed_count} 个重复chunks")
            
            return {
                "total_chunks": len(chunks),
                "duplicates_removed": removed_count,
                "remaining_chunks": len(chunks) - removed_count,
                "message": f"成功清理 {removed_count} 个重复chunks"
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"清理重复chunks失败: {e}")
            raise Exception(f"清理重复chunks失败: {str(e)}")