from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
import json
import asyncio
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import uuid
import time

from app.models.chunk import Chunk, IngestionJob
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.models.page_screenshot import PageScreenshot
from app.processors.processor_factory import ProcessorFactory
from app.utils.ai_utils import AIUtils
from app.utils.text_splitter import TextSplitter
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
        self.text_splitter = TextSplitter()
        self.doc_repo = DocumentRepository(db)
        self.milvus_repo = MilvusRepository()
        self.kb_service = KBService(db)

    async def start_ingestion_job(self, kb_id: str, document_id: str, user_id: str, 
                                  skip_tagging: bool = False) -> str:
        """启动文档摄入任务（v2版本：异步处理）
        
        Args:
            kb_id: 知识库ID
            document_id: 文档ID
            user_id: 用户ID
            skip_tagging: 是否跳过标签生成步骤（默认False）
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
                job_id, kb_id, document_id, skip_tagging,
                timeout=300  # 5分钟超时
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

    def _run_pipeline_sync(self, job_id: str, kb_id: str, document_id: str, skip_tagging: bool = False):
        """同步版本的流水线执行（在线程池中运行）"""
        # 创建新的数据库会话
        db = SessionLocal()
        try:
            logger.info(f"开始处理任务 {job_id}")
            # 更新任务状态
            job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
            if not job:
                raise Exception(f"任务不存在: {job_id}")

            job.status = "processing"
            db.commit()
            logger.info(f"任务状态更新为 processing: {job_id}")

            # 执行摄取流水线
            self._execute_pipeline(db, job_id, kb_id, document_id, skip_tagging)

            # 更新任务状态为完成
            job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
            if job:
                job.status = "completed"
                db.commit()
                logger.info(f"任务完成: {job_id}")

        except Exception as e:
            logger.error(f"任务执行失败: {job_id}, 错误: {str(e)}")
            # 更新任务状态为失败
            db.rollback()  # 回滚事务
            job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = str(e)
                db.commit()
            raise e
        finally:
            db.close()

    def _execute_pipeline(self, db: Session, job_id: str, kb_id: str, document_id: str, skip_tagging: bool = False):
        """执行摄取流水线的核心逻辑
        
        Args:
            skip_tagging: 是否跳过标签生成步骤，如果为True，则chunks将以空标签存储
        """
        logger.info(f"开始执行摄取流水线: job_id={job_id}, document_id={document_id}, skip_tagging={skip_tagging}")
        
        # 1. 获取文档路径（预加载物理文件信息）
        document = db.query(Document).options(
            joinedload(Document.physical_file)
        ).filter(Document.id == document_id).first()

        if not document:
            raise Exception(f"文档不存在: {document_id}")

        if not document.physical_file:
            raise Exception(f"文档对应的物理文件不存在: {document_id}")

        logger.info(f"文档信息获取成功: {document.filename}")

        # 2. 获取知识库的标签字典（即使跳过标签生成也要获取，以备后用）
        kb_service = KBService(db)
        kb = kb_service.get_kb_by_id(kb_id)
        if not kb:
            raise Exception(f"知识库不存在: {kb_id}")

        tag_directory = kb.tag_dictionary if not skip_tagging else None
        logger.info(f"知识库信息获取成功: {kb.name}, 标签字典: {'存在' if tag_directory else '不存在/跳过'}")

        # 3. 确保Milvus Collection存在
        collection_name = self._ensure_milvus_collection(db, kb)
        logger.info(f"Milvus Collection 准备完成: {collection_name}")

        # 4. 选择合适的处理器（使用物理文件路径）
        file_path = document.physical_file.file_path
        processor = self.processor_factory.get_processor(file_path)
        if not processor:
            raise Exception(f"不支持的文件类型: {file_path}")

        # 5. 提取文档内容，processor现在可能返回截图路径
        markdown_text, screenshot_paths = processor.extract_content(file_path)
        
        # 6. 处理页面截图（如果存在）
        screenshot_service = ScreenshotService(db)
        page_screenshots = []
        screenshot_id_mapping = {}
        
        if screenshot_paths:
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
            logger.debug("处理器未返回截图路径")

        # 7. 分割文本为chunks
        logger.debug(f"开始分割文本，原始长度: {len(markdown_text)} 字符")
        chunks = self.text_splitter.split_text(markdown_text)
        logger.info(f"分割后的chunks数量: {len(chunks)}")

        # 8. 为每个chunk生成标签、嵌入向量并建立截图关联
        chunk_records = []
        milvus_data = []

        for i, chunk_text in enumerate(chunks):
            chunk_id = str(uuid.uuid4())
            
            # 打印正在处理的chunk信息
            logger.debug(f"\n处理 Chunk {i}:")
            logger.debug(f"Chunk内容长度: {len(chunk_text)} 字符")
            logger.debug(f"Chunk内容预览: {chunk_text[:100]}...")

            # 8.1. 根据配置决定是否生成标签
            tags = []
            if skip_tagging:
                logger.debug("跳过标签生成步骤")
            else:
                # 使用知识库的标签字典生成标签
                tags = self.ai_utils.generate_tags(chunk_text, tag_directory)
                logger.debug(f"生成标签: {tags}")

            # 8.2. 生成嵌入向量
            embedding = self.ai_utils.generate_embedding(chunk_text)
            logger.debug(f"生成嵌入向量，维度: {len(embedding)}")
            
            screenshot_ids = self._associate_chunks_with_screenshots([chunk_text], screenshot_id_mapping, len(page_screenshots))[0]
            logger.debug(f"关联的截图IDs: {screenshot_ids}")

            # 8.3. 创建Chunk记录
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

            # 8.4. 准备Milvus数据
            milvus_data.append({
                "id": chunk_id,
                "text": chunk_text,
                "embedding": embedding,
                "metadata": {
                    "kb_id": kb_id,
                    "document_id": document_id,
                    "chunk_index": i,
                    "tags": tags,
                    "screenshot_ids": screenshot_ids
                }
            })

        # 9. 批量保存chunks到SQLite
        logger.info(f"\n批量保存 {len(chunk_records)} 个chunks到数据库")
        db.add_all(chunk_records)
        db.commit()

        # 10. 批量保存chunks到Milvus
        logger.info(f"准备保存 {len(milvus_data)} 个chunks到Milvus")
        try:
            self.milvus_repo.insert_chunks(collection_name, milvus_data)
            logger.info(f"成功保存 {len(milvus_data)} 个chunks到Milvus")
        except Exception as e:
            logger.error(f"保存到Milvus失败: {str(e)}")
            # 注意：不要因为Milvus失败而回滚SQLite，数据一致性由业务逻辑保证

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
        # 如果已经有collection_id，先检查是否真的存在
        if kb.milvus_collection_id:
            collection_name = self.milvus_repo._normalize_collection_name(kb.id)
            # 检查collection是否真的存在
            if self.milvus_repo._collection_exists(kb.id):
                return kb.milvus_collection_id
            else:
                # collection不存在，需要重新创建
                logger.warning(f"警告: 知识库 {kb.id} 的collection {kb.milvus_collection_id} 不存在，将重新创建")

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