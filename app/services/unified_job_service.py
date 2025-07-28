"""
统一任务服务
文件: unified_job_service.py
创建时间: 2025-07-26
描述: 统一任务系统的核心服务，管理解析和索引任务
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.db.database import get_db
from app.models.job import Job, Task, JobType, JobStatus, TaskType, TaskStatus, TargetType
from app.models.document import PhysicalDocument
from app.models.fragment import Fragment
from app.schemas.job import (
    CreateParseJobRequest, CreateIndexJobRequest, CreateBatchJobRequest,
    JobResponse, JobDetailResponse, JobListResponse, JobStatsResponse, QueueStatsResponse, TaskResponse
)
from app.utils.task_queue import AsyncTaskQueue, task_queue
from app.services.fragment_parser_service import FragmentParserService
from app.services.index_service import IndexService

logger = logging.getLogger(__name__)


class UnifiedJobService:
    """统一任务服务"""

    def __init__(self):
        # 使用全局任务队列实例
        self.task_queue = task_queue

    def _serialize_for_json(self, obj):
        """自定义JSON序列化函数，处理datetime等不可序列化的对象"""
        if isinstance(obj, dict):
            return {key: self._serialize_for_json(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._serialize_for_json(item) for item in obj]
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            return self._serialize_for_json(obj.__dict__)
        else:
            return obj

    async def start(self):
        """启动任务队列"""
        await self.task_queue.start()
        logger.info("统一任务服务已启动")

    async def stop(self):
        """停止任务队列"""
        await self.task_queue.stop()
        logger.info("统一任务服务已停止")

    # 任务提交接口
    async def submit_job(self, job: Job, tasks: List[Task], db: Session):
        """提交任务到队列"""
        try:
            # 提交任务到队列
            for task in tasks:
                if task.task_type == TaskType.PARSE_DOCUMENT.value:
                    await self.task_queue.add_task(
                        self._execute_parse_task,
                        task.id,
                        timeout=300
                    )
                elif task.task_type == TaskType.INDEX_FRAGMENT.value:
                    await self.task_queue.add_task(
                        self._execute_index_task,
                        task.id,
                        timeout=300
                    )
                elif task.task_type == TaskType.PARSE_AND_INDEX_DOCUMENT.value:
                    await self.task_queue.add_task(
                        self._execute_parse_and_index_task,
                        task.id,
                        timeout=600  # 解析+索引需要更长时间
                    )
                else:
                    logger.warning(f"未知任务类型: {task.task_type}")

            # 更新Job状态
            job.status = JobStatus.RUNNING.value
            job.started_at = datetime.utcnow()
            db.commit()

        except Exception as e:
            logger.error(f"提交任务失败: {e}")
            job.status = JobStatus.FAILED.value
            job.error_message = str(e)
            db.commit()
            raise

    # 任务执行
    def _execute_parse_task(self, task_id: str):
        """执行解析任务"""
        # 在新的事件循环中运行异步任务
        import asyncio
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(self._execute_parse_task_async(task_id))
        except Exception as e:
            logger.error(f"解析任务执行异常: {e}")
            raise
        finally:
            # 确保事件循环正确关闭
            if loop and not loop.is_closed():
                try:
                    # 等待所有待处理的任务完成
                    pending = asyncio.all_tasks(loop)
                    if pending:
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except Exception as e:
                    logger.warning(f"清理待处理任务时出错: {e}")
                finally:
                    loop.close()

    async def _execute_parse_task_async(self, task_id: str):
        """异步执行解析任务"""
        from app.db.database import SessionLocal

        # 为任务状态更新创建独立的数据库会话
        status_db = SessionLocal()
        try:
            task = status_db.query(Task).filter(Task.id == task_id).first()
            if not task:
                logger.error(f"任务不存在: {task_id}")
                return

            # 标记任务开始
            task.mark_started(worker_id="parser_worker")
            status_db.commit()

            # 执行解析 - 为解析操作创建独立的数据库会话
            parse_db = SessionLocal()
            try:
                # 创建解析服务实例
                parser_service = FragmentParserService()

                result = await parser_service.parse_document_fragments(
                    db=parse_db,
                    kb_id=task.job.kb_id,
                    document_id=task.target_id,
                    force_reparse=task.config_dict.get('force_reparse', False)
                )

                # 解析成功，更新任务状态
                # 重新获取任务对象（因为使用了不同的会话）
                task = status_db.query(Task).filter(Task.id == task_id).first()

                # 将解析结果转换为字典以便JSON序列化
                result_dict = None
                if result:
                    if hasattr(result, 'model_dump'):
                        # Pydantic v2 - 使用mode='json'确保datetime等对象被正确序列化
                        result_dict = result.model_dump(mode='json')
                    elif hasattr(result, 'dict'):
                        # Pydantic v1 - 使用自定义序列化函数
                        result_dict = self._serialize_for_json(result.dict())
                    elif isinstance(result, list):
                        # 如果是列表，处理每个元素
                        result_dict = []
                        for item in result:
                            if hasattr(item, 'model_dump'):
                                result_dict.append(item.model_dump(mode='json'))
                            elif hasattr(item, 'dict'):
                                result_dict.append(self._serialize_for_json(item.dict()))
                            else:
                                result_dict.append(str(item))
                    else:
                        # 如果不是Pydantic对象，尝试转换为字典
                        result_dict = self._serialize_for_json(dict(result)) if hasattr(result, '__dict__') else str(result)

                task.mark_completed(result=result_dict)
                status_db.commit()

                # 更新Job进度
                self._update_job_progress(task.job_id, status_db)

            except Exception as e:
                logger.error(f"解析任务执行失败: {e}")
                # 重新获取任务对象（因为使用了不同的会话）
                task = status_db.query(Task).filter(Task.id == task_id).first()
                task.mark_failed(str(e))
                status_db.commit()

                # 更新Job进度
                self._update_job_progress(task.job_id, status_db)

            finally:
                parse_db.close()

        except Exception as e:
            logger.error(f"解析任务处理失败: {e}")
            status_db.rollback()
        finally:
            status_db.close()

    def _execute_index_task(self, task_id: str):
        """执行索引任务"""
        # 在新的事件循环中运行异步任务
        import asyncio
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(self._execute_index_task_async(task_id))
        except Exception as e:
            logger.error(f"索引任务执行异常: {e}")
            raise
        finally:
            # 确保事件循环正确关闭
            if loop and not loop.is_closed():
                try:
                    # 等待所有待处理的任务完成
                    pending = asyncio.all_tasks(loop)
                    if pending:
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except Exception as e:
                    logger.warning(f"清理待处理任务时出错: {e}")
                finally:
                    loop.close()

    async def _execute_index_task_async(self, task_id: str):
        """异步执行索引任务"""
        from app.db.database import SessionLocal

        # 为任务状态更新创建独立的数据库会话
        status_db = SessionLocal()
        try:
            task = status_db.query(Task).filter(Task.id == task_id).first()
            if not task:
                logger.error(f"任务不存在: {task_id}")
                return

            # 标记任务开始
            task.mark_started(worker_id="index_worker")
            status_db.commit()

            # 执行索引 - 为索引操作创建独立的数据库会话
            index_db = SessionLocal()
            try:
                # 获取任务配置
                config = task.config_dict
                force_regenerate = config.get('force_regenerate', False)
                max_tags = config.get('max_tags', 20)

                # 创建索引服务实例
                index_service = IndexService(db=index_db, kb_id=task.job.kb_id)

                result = await index_service.create_fragment_index(
                    fragment_id=task.target_id,
                    force_regenerate=force_regenerate,
                    max_tags=max_tags
                )

                # 索引成功，更新任务状态
                # 重新获取任务对象（因为使用了不同的会话）
                task = status_db.query(Task).filter(Task.id == task_id).first()

                # 将IndexResponse转换为字典以便JSON序列化
                result_dict = None
                if result:
                    if hasattr(result, 'model_dump'):
                        # Pydantic v2 - 使用mode='json'确保datetime等对象被正确序列化
                        result_dict = result.model_dump(mode='json')
                    elif hasattr(result, 'dict'):
                        # Pydantic v1 - 使用自定义序列化函数
                        result_dict = self._serialize_for_json(result.dict())
                    else:
                        # 如果不是Pydantic对象，尝试转换为字典
                        result_dict = self._serialize_for_json(dict(result)) if hasattr(result, '__dict__') else str(result)

                task.mark_completed(result=result_dict)
                status_db.commit()

                # 更新Job进度
                self._update_job_progress(task.job_id, status_db)

            except Exception as e:
                logger.error(f"索引任务执行失败: {e}")
                # 重新获取任务对象（因为使用了不同的会话）
                task = status_db.query(Task).filter(Task.id == task_id).first()
                task.mark_failed(str(e))
                status_db.commit()

                # 更新Job进度
                self._update_job_progress(task.job_id, status_db)

            finally:
                index_db.close()

        except Exception as e:
            logger.error(f"索引任务处理失败: {e}")
            status_db.rollback()
        finally:
            status_db.close()

    def _execute_parse_and_index_task(self, task_id: str):
        """执行解析+索引任务"""
        # 在新的事件循环中运行异步任务
        import asyncio
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(self._execute_parse_and_index_task_async(task_id))
        except Exception as e:
            logger.error(f"解析+索引任务执行异常: {e}")
            raise
        finally:
            # 确保事件循环正确关闭
            if loop and not loop.is_closed():
                try:
                    # 等待所有待处理的任务完成
                    pending = asyncio.all_tasks(loop)
                    if pending:
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except Exception as e:
                    logger.warning(f"清理待处理任务时出错: {e}")
                finally:
                    loop.close()

    async def _execute_parse_and_index_task_async(self, task_id: str):
        """异步执行解析+索引任务"""
        from app.db.database import SessionLocal

        # 为任务状态更新创建独立的数据库会话
        status_db = SessionLocal()
        try:
            task = status_db.query(Task).filter(Task.id == task_id).first()
            if not task:
                logger.error(f"任务不存在: {task_id}")
                return

            # 标记任务开始
            task.mark_started(worker_id="parse_index_worker")
            status_db.commit()

            # 第一步：执行解析
            parse_db = SessionLocal()
            try:
                # 创建解析服务实例
                parser_service = FragmentParserService()

                parse_result = await parser_service.parse_document_fragments(
                    db=parse_db,
                    kb_id=task.job.kb_id,
                    document_id=task.target_id,
                    force_reparse=task.config_dict.get('force_reparse', True)
                )

                logger.info(f"文档 {task.target_id} 解析完成，开始索引")

            except Exception as e:
                logger.error(f"解析阶段失败: {e}")
                # 重新获取任务对象（因为使用了不同的会话）
                task = status_db.query(Task).filter(Task.id == task_id).first()
                task.mark_failed(f"解析阶段失败: {str(e)}")
                status_db.commit()

                # 更新Job进度
                self._update_job_progress(task.job_id, status_db)
                return

            finally:
                parse_db.close()

            # 第二步：执行索引
            index_db = SessionLocal()
            try:
                # 获取解析后的Fragment
                fragments = index_db.query(Fragment).filter(
                    Fragment.document_id == task.target_id,
                    Fragment.fragment_type == "text"
                ).all()

                if not fragments:
                    logger.warning(f"文档 {task.target_id} 解析后没有找到Fragment")
                    # 重新获取任务对象
                    task = status_db.query(Task).filter(Task.id == task_id).first()
                    task.mark_failed("解析后没有找到Fragment")
                    status_db.commit()

                    # 更新Job进度
                    self._update_job_progress(task.job_id, status_db)
                    return

                # 获取任务配置
                config = task.config_dict
                force_regenerate = config.get('force_regenerate', False)
                max_tags = config.get('max_tags', 20)
                enable_multimodal = config.get('enable_multimodal', False)
                multimodal_config = config.get('multimodal_config', {})

                # 创建索引服务实例
                index_service = IndexService(db=index_db, kb_id=task.job.kb_id)

                # 为每个Fragment创建索引
                indexed_fragments = []
                failed_fragments = []

                for fragment in fragments:
                    try:
                        index_result = await index_service.create_fragment_index(
                            fragment_id=fragment.id,
                            force_regenerate=force_regenerate,
                            max_tags=max_tags,
                            enable_multimodal=enable_multimodal,
                            multimodal_config=multimodal_config
                        )
                        indexed_fragments.append({
                            'fragment_id': fragment.id,
                            'result': index_result.model_dump(mode='json') if hasattr(index_result, 'model_dump') else str(index_result)
                        })
                    except Exception as e:
                        logger.error(f"Fragment {fragment.id} 索引失败: {e}")
                        failed_fragments.append({
                            'fragment_id': fragment.id,
                            'error': str(e)
                        })

                # 准备结果
                result_dict = {
                    'parse_result': parse_result.model_dump(mode='json') if hasattr(parse_result, 'model_dump') else str(parse_result),
                    'indexed_fragments': indexed_fragments,
                    'failed_fragments': failed_fragments,
                    'total_fragments': len(fragments),
                    'successful_indexes': len(indexed_fragments),
                    'failed_indexes': len(failed_fragments)
                }

                # 更新任务状态
                # 重新获取任务对象（因为使用了不同的会话）
                task = status_db.query(Task).filter(Task.id == task_id).first()

                if failed_fragments:
                    # 部分失败
                    task.mark_failed(f"索引阶段部分失败: {len(failed_fragments)}/{len(fragments)} 个Fragment索引失败")
                    task.result_dict = result_dict
                else:
                    # 全部成功
                    task.mark_completed(result=result_dict)

                status_db.commit()

                # 更新Job进度
                self._update_job_progress(task.job_id, status_db)

            except Exception as e:
                logger.error(f"索引阶段失败: {e}")
                # 重新获取任务对象（因为使用了不同的会话）
                task = status_db.query(Task).filter(Task.id == task_id).first()
                task.mark_failed(f"索引阶段失败: {str(e)}")
                status_db.commit()

                # 更新Job进度
                self._update_job_progress(task.job_id, status_db)

            finally:
                index_db.close()

        except Exception as e:
            logger.error(f"解析+索引任务处理失败: {e}")
            status_db.rollback()
        finally:
            status_db.close()

    def _update_job_progress(self, job_id: str, db: Session):
        """更新任务进度"""
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.update_progress()
                db.commit()
        except Exception as e:
            logger.error(f"更新任务进度失败: {e}")
            db.rollback()

    # 查询方法
    def get_job(self, job_id: str, db: Session) -> Optional[JobDetailResponse]:
        """获取任务详情"""
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return None

        # 手动创建JobDetailResponse以确保config字段正确序列化
        return JobDetailResponse(
            id=job.id,
            kb_id=job.kb_id,
            job_type=job.job_type,
            status=job.status,
            priority=job.priority,
            config=job.config_dict,  # 使用config_dict属性获取字典
            total_tasks=job.total_tasks,
            completed_tasks=job.completed_tasks,
            failed_tasks=job.failed_tasks,
            progress_percentage=job.progress_percentage,
            error_message=job.error_message,
            created_at=job.created_at,
            updated_at=job.updated_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            created_by=job.created_by,
            tasks=[
                TaskResponse(
                    id=task.id,
                    job_id=task.job_id,
                    task_type=task.task_type,
                    status=task.status,
                    target_id=task.target_id,
                    target_type=task.target_type,
                    config=task.config_dict,  # 使用config_dict属性获取字典
                    worker_id=task.worker_id,
                    retry_count=task.retry_count,
                    max_retries=task.max_retries,
                    result=task.result_dict,  # 使用result_dict属性获取字典
                    error_message=task.error_message,
                    created_at=task.created_at,
                    updated_at=task.updated_at,
                    started_at=task.started_at,
                    completed_at=task.completed_at
                ) for task in job.tasks
            ]
        )

    def list_jobs(
        self,
        kb_id: Optional[str] = None,
        job_type: Optional[JobType] = None,
        status: Optional[JobStatus] = None,
        page: int = 1,
        page_size: int = 20,
        db: Session = None
    ) -> JobListResponse:
        """获取任务列表"""
        if db is None:
            db = next(get_db())

        query = db.query(Job)

        # 过滤条件
        if kb_id:
            query = query.filter(Job.kb_id == kb_id)
        if job_type:
            query = query.filter(Job.job_type == job_type.value)
        if status:
            query = query.filter(Job.status == status.value)

        # 分页
        total = query.count()
        jobs = query.order_by(Job.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

        return JobListResponse(
            jobs=[
                JobResponse(
                    id=job.id,
                    kb_id=job.kb_id,
                    job_type=job.job_type,
                    status=job.status,
                    priority=job.priority,
                    config=job.config_dict,  # 使用config_dict属性获取字典
                    total_tasks=job.total_tasks,
                    completed_tasks=job.completed_tasks,
                    failed_tasks=job.failed_tasks,
                    progress_percentage=job.progress_percentage,
                    error_message=job.error_message,
                    created_at=job.created_at,
                    updated_at=job.updated_at,
                    started_at=job.started_at,
                    completed_at=job.completed_at,
                    created_by=job.created_by
                ) for job in jobs
            ],
            total=total,
            page=page,
            page_size=page_size
        )

    def get_job_stats(self, kb_id: Optional[str] = None, db: Session = None) -> JobStatsResponse:
        """获取任务统计"""
        if db is None:
            db = next(get_db())

        query = db.query(Job)
        if kb_id:
            query = query.filter(Job.kb_id == kb_id)

        stats = query.with_entities(
            func.count(Job.id).label('total'),
            func.sum(func.case([(Job.status == JobStatus.PENDING.value, 1)], else_=0)).label('pending'),
            func.sum(func.case([(Job.status == JobStatus.RUNNING.value, 1)], else_=0)).label('running'),
            func.sum(func.case([(Job.status == JobStatus.COMPLETED.value, 1)], else_=0)).label('completed'),
            func.sum(func.case([(Job.status == JobStatus.FAILED.value, 1)], else_=0)).label('failed'),
            func.sum(func.case([(Job.status == JobStatus.CANCELLED.value, 1)], else_=0)).label('cancelled'),
        ).first()

        return JobStatsResponse(
            total_jobs=stats.total or 0,
            pending_jobs=stats.pending or 0,
            running_jobs=stats.running or 0,
            completed_jobs=stats.completed or 0,
            failed_jobs=stats.failed or 0,
            cancelled_jobs=stats.cancelled or 0
        )

    def get_queue_stats(self) -> QueueStatsResponse:
        """获取队列统计"""
        stats = self.task_queue.get_queue_stats()

        return QueueStatsResponse(
            total_tasks=stats.get('total_tasks', 0),
            pending_tasks=stats.get('pending', 0),
            running_tasks=stats.get('running', 0),
            completed_tasks=stats.get('completed', 0),
            failed_tasks=stats.get('failed', 0),
            cancelled_tasks=stats.get('timeout', 0),  # 将 timeout 映射为 cancelled
            active_workers=len(self.task_queue.running_tasks),
            queue_size=stats.get('pending', 0)
        )

    async def retry_job(self, job_id: str, db: Session) -> bool:
        """重试任务"""
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                logger.error(f"任务不存在: {job_id}")
                return False

            # 只有失败的任务才能重试
            if job.status not in [JobStatus.FAILED.value, JobStatus.CANCELLED.value]:
                logger.warning(f"任务状态不允许重试: {job.status}，只有失败或取消的任务才能重试")
                return False

            # 重置失败的任务状态
            failed_tasks = db.query(Task).filter(
                and_(
                    Task.job_id == job_id,
                    Task.status.in_([TaskStatus.FAILED.value, TaskStatus.TIMEOUT.value])
                )
            ).all()

            if not failed_tasks:
                logger.warning(f"没有找到失败的任务: {job_id}")
                return False

            # 重置任务状态
            for task in failed_tasks:
                task.status = TaskStatus.PENDING.value
                task.worker_id = None
                task.error_message = None
                task.started_at = None
                task.completed_at = None
                task.retry_count += 1
                task.updated_at = datetime.utcnow()

            # 重置任务状态
            job.status = JobStatus.PENDING.value
            job.error_message = None
            job.started_at = None
            job.completed_at = None
            job.updated_at = datetime.utcnow()

            db.commit()

            # 重新提交任务到队列
            await self.submit_job(job, failed_tasks, db)

            logger.info(f"任务重试成功: {job_id}, 重试任务数: {len(failed_tasks)}")
            return True

        except Exception as e:
            logger.error(f"重试任务失败: {e}")
            db.rollback()
            return False


# 全局实例
unified_job_service = UnifiedJobService()