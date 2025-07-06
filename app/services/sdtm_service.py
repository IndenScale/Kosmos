import asyncio
import json
import uuid
import logging
from sqlalchemy.orm import Session
from typing import Dict, List, Optional, Any
from datetime import datetime

from app.models.sdtm import (
    SDTMMode, ProgressMetrics, QualityMetrics, 
    DocumentInfo, AbnormalDocument, EditOperation, 
    DocumentAnnotation, SDTMEngineResponse, SDTMStats, SDTMJob
)
from app.db.database import SessionLocal
from app.models.knowledge_base import KnowledgeBase
from app.models.chunk import Chunk
from app.services.sdtm_engine import SDTMEngine
from app.services.sdtm_stats_service import SDTMStatsService
from app.services.kb_service import KBService
from app.repositories.chunk_repo import ChunkRepository

# 配置日志
logger = logging.getLogger(__name__)

class SDTMService:
    """SDTM服务 - 智能标签生成与标签字典优化系统
    
    SDTM (Streaming Domain Topic Modeling) 的核心功能：
    1. 替代传统的文档标签生成过程
    2. 基于已摄入的chunks生成智能标签
    3. 优化和维护知识库的标签字典
    4. 同时更新SQLite和Milvus中的标签记录
    
    工作流程：
    - 读取已摄入的chunks（无标签或需要重新标注）
    - 使用LLM生成智能标签
    - 优化标签字典结构
    - 更新chunk的标签字段
    - 同步更新向量数据库中的记录
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.engine = SDTMEngine()
        self.stats_service = SDTMStatsService(db)
        self.kb_service = KBService(db)
        self.chunk_repo = ChunkRepository(db)
    
    async def start_sdtm_job(
        self, 
        kb_id: str, 
        mode: SDTMMode, 
        batch_size: int = 10, 
        auto_apply: bool = True,
        abnormal_doc_slots: int = 3,
        normal_doc_slots: int = 7,
        max_iterations: int = 50,
        abnormal_doc_threshold: float = 3.0,
        enable_early_termination: bool = True
    ) -> str:
        """启动SDTM任务（异步处理）
        
        Args:
            kb_id: 知识库ID
            mode: 处理模式
            batch_size: 批处理大小
            auto_apply: 是否自动应用操作
            abnormal_doc_slots: 异常文档处理槽位
            normal_doc_slots: 正常文档处理槽位
            max_iterations: 最大迭代次数
            abnormal_doc_threshold: 异常文档阈值（百分比）
            enable_early_termination: 是否启用提前终止
            
        Returns:
            任务ID
        """
        # 创建任务记录
        job_id = str(uuid.uuid4())
        job = SDTMJob(
            id=job_id,
            kb_id=kb_id,
            mode=mode.value,
            batch_size=batch_size,
            auto_apply=auto_apply,
            status="pending"
        )
        self.db.add(job)
        self.db.commit()

        try:
            # 确保任务队列已启动
            from app.utils.task_queue import task_queue
            if not task_queue._running:
                logger.warning("任务队列未运行，尝试启动...")
                await task_queue.start()
            
            logger.debug(f"任务队列状态: running={task_queue._running}, worker_task={task_queue._worker_task}")
            
            # 将任务添加到异步队列
            task_id = await task_queue.add_task(
                self._run_sdtm_sync,
                job_id, kb_id, mode, batch_size, auto_apply,
                abnormal_doc_slots, normal_doc_slots, max_iterations,
                abnormal_doc_threshold, enable_early_termination,
                timeout=600  # 10分钟超时
            )

            # 更新job记录，关联task_id
            job.task_id = task_id
            self.db.commit()
            
            logger.info(f"SDTM任务已添加到队列: {job_id}, 队列任务ID: {task_id}")
            
            return job_id

        except Exception as e:
            # 如果添加任务失败，更新任务状态
            job.status = "failed"
            job.error_message = str(e)
            self.db.commit()
            raise e
    
    def _run_sdtm_sync(
        self, 
        job_id: str, 
        kb_id: str, 
        mode: SDTMMode, 
        batch_size: int, 
        auto_apply: bool,
        abnormal_doc_slots: int = 3,
        normal_doc_slots: int = 7,
        max_iterations: int = 50,
        abnormal_doc_threshold: float = 3.0,
        enable_early_termination: bool = True
    ):
        """同步版本的SDTM处理（在线程池中运行）"""
        # 创建新的数据库会话
        db = SessionLocal()
        try:
            logger.info(f"开始处理SDTM任务: {job_id}")
            
            # 更新任务状态
            job = db.query(SDTMJob).filter(SDTMJob.id == job_id).first()
            if not job:
                raise Exception(f"SDTM任务不存在: {job_id}")

            job.status = "processing"
            db.commit()
            logger.info(f"SDTM任务状态更新为 processing: {job_id}")

            # 创建新的服务实例（使用新的数据库会话）
            sdtm_service = SDTMService(db)
            
            # 执行SDTM处理
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            processing_success = False
            sdtm_result = None
            
            try:
                logger.info("开始执行SDTM处理...")
                result = loop.run_until_complete(
                    sdtm_service.process_knowledge_base(
                        kb_id=kb_id,
                        mode=mode,
                        batch_size=batch_size,
                        auto_apply=auto_apply,
                        max_iterations=max_iterations,
                        abnormal_doc_slots=abnormal_doc_slots,
                        normal_doc_slots=normal_doc_slots,
                        abnormal_doc_threshold=abnormal_doc_threshold,
                        enable_early_termination=enable_early_termination
                    )
                )
                sdtm_result = result
                processing_success = True
                logger.info("SDTM处理执行成功")
                
            except Exception as processing_error:
                logger.error(f"SDTM处理执行失败: {processing_error}")
                import traceback
                logger.error(f"详细错误信息: {traceback.format_exc()}")
                processing_success = False
                sdtm_result = {
                    "success": False,
                    "message": f"SDTM处理失败: {str(processing_error)}",
                    "error": str(processing_error)
                }
            finally:
                loop.close()
            
            # 更新任务状态
            job = db.query(SDTMJob).filter(SDTMJob.id == job_id).first()
            if job:
                if processing_success:
                    job.status = "completed"
                    logger.info(f"SDTM任务状态标记为完成: {job_id}")
                else:
                    job.status = "failed"
                    job.error_message = sdtm_result.get("error", "SDTM处理失败") if isinstance(sdtm_result, dict) else "SDTM处理失败"
                    logger.error(f"SDTM任务状态标记为失败: {job_id}")
                
                # 尝试序列化结果（失败不影响主要功能）
                try:
                    if sdtm_result:
                        # 使用新的服务实例进行序列化测试
                        if not sdtm_service.test_serialization(sdtm_result):
                            raise Exception("预序列化测试失败")
                        
                        serializable_result = sdtm_service._make_result_serializable(sdtm_result)
                        job.result = json.dumps(serializable_result, ensure_ascii=False)
                        logger.info(f"SDTM任务结果序列化成功: {job_id}")
                    
                except Exception as serialization_error:
                    logger.warning(f"SDTM任务结果序列化失败（不影响主功能）: {serialization_error}")
                    
                    # 提供简化的结果信息
                    fallback_result = {
                        "success": processing_success,
                        "message": sdtm_result.get("message", "任务完成") if isinstance(sdtm_result, dict) else "任务完成",
                        "operations_count": len(sdtm_result.get("operations", [])) if isinstance(sdtm_result, dict) else 0,
                        "annotations_count": len(sdtm_result.get("annotations", [])) if isinstance(sdtm_result, dict) else 0,
                        "serialization_error": f"结果序列化失败: {str(serialization_error)}",
                        "completed_at": datetime.now().isoformat()
                    }
                    job.result = json.dumps(fallback_result, ensure_ascii=False)
                    logger.warning(f"SDTM任务使用简化结果保存: {job_id}")
                
                # 提交任务状态更新（无论序列化是否成功）
                db.commit()
                logger.info(f"SDTM任务状态已提交到数据库: {job_id}")
                
                # 验证标签字典是否确实被更新了
                if processing_success:
                    self._verify_tag_dictionary_update(db, kb_id, job_id)

        except Exception as e:
            print(f"💥 SDTM任务执行过程中发生严重错误: {job_id}, 错误: {str(e)}")
            import traceback
            print(f"💥 严重错误的详细信息: {traceback.format_exc()}")
            
            # 只在确实需要时才回滚（比如数据库连接错误等）
            try:
                # 尝试更新任务状态为失败，但不回滚之前可能已经成功的操作
                job = db.query(SDTMJob).filter(SDTMJob.id == job_id).first()
                if job:
                    job.status = "failed"
                    job.error_message = str(e)
                    db.commit()
                    logger.info(f"已将任务状态更新为失败: {job_id}")
                else:
                    logger.warning(f"无法找到任务记录: {job_id}")
            except Exception as status_update_error:
                logger.warning(f"更新任务状态时出错: {status_update_error}")
                # 如果任务状态更新失败，说明数据库有严重问题，此时才回滚
                logger.warning("数据库状态有问题，执行回滚操作")
                db.rollback()
                
                # 再次尝试更新任务状态
                try:
                    job = db.query(SDTMJob).filter(SDTMJob.id == job_id).first()
                    if job:
                        job.status = "failed"
                        job.error_message = f"严重错误: {str(e)} | 状态更新错误: {str(status_update_error)}"
                        db.commit()
                except:
                    logger.error("无法更新任务状态，数据库可能有严重问题")
            
            logger.info(f"SDTM任务处理完成，即使发生了错误: {job_id}")
        finally:
            logger.debug(f"关闭数据库会话: {job_id}")
            db.close()
    
    def get_sdtm_job_status(self, job_id: str) -> Optional[SDTMJob]:
        """获取SDTM任务状态"""
        job = self.db.query(SDTMJob).filter(SDTMJob.id == job_id).first()
        if not job:
            return None

        # 如果任务有task_id，检查队列中的状态
        if hasattr(job, 'task_id') and job.task_id:
            from app.utils.task_queue import task_queue
            queue_task = task_queue.get_task_status(job.task_id)
            if queue_task:
                # 同步队列状态到数据库
                from app.utils.task_queue import TaskStatus
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
    
    def get_kb_sdtm_jobs(self, kb_id: str) -> List[SDTMJob]:
        """获取知识库的所有SDTM任务"""
        return self.db.query(SDTMJob).filter(
            SDTMJob.kb_id == kb_id
        ).order_by(SDTMJob.created_at.desc()).all()
    
    def _make_result_serializable(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """将结果转换为可JSON序列化的格式"""
        from datetime import datetime, date
        
        def _convert_value(value):
            """递归转换单个值"""
            # 处理datetime对象
            if isinstance(value, datetime):
                return value.isoformat()
            elif isinstance(value, date):
                return value.isoformat()
            # 处理自定义对象
            elif hasattr(value, '__dict__') and hasattr(value, '__class__'):
                # 检查是否是Pydantic模型
                if hasattr(value, 'dict'):
                    try:
                        return _convert_value(value.dict())
                    except Exception as e:
                        print(f"Error converting Pydantic model to dict: {e}")
                        return str(value)
                # 检查是否是SQLAlchemy模型或其他对象
                else:
                    try:
                        # 尝试转换为字典
                        if hasattr(value, '__table__'):  # SQLAlchemy模型
                            obj_dict = {}
                            for column in value.__table__.columns:
                                col_value = getattr(value, column.name, None)
                                obj_dict[column.name] = _convert_value(col_value)
                            return obj_dict
                        else:
                            # 通用对象转换
                            obj_dict = {}
                            for attr_name in dir(value):
                                if not attr_name.startswith('_') and not callable(getattr(value, attr_name)):
                                    try:
                                        attr_value = getattr(value, attr_name)
                                        obj_dict[attr_name] = _convert_value(attr_value)
                                    except:
                                        continue
                            return obj_dict if obj_dict else str(value)
                    except Exception as e:
                        print(f"Error converting object {type(value)}: {e}")
                        return str(value)
            # 处理字典
            elif isinstance(value, dict):
                return {k: _convert_value(v) for k, v in value.items()}
            # 处理列表
            elif isinstance(value, list):
                return [_convert_value(item) for item in value]
            # 处理元组
            elif isinstance(value, tuple):
                return [_convert_value(item) for item in value]
            # 处理集合
            elif isinstance(value, set):
                return [_convert_value(item) for item in value]
            # 基础类型直接返回
            elif isinstance(value, (str, int, float, bool, type(None))):
                return value
            # 其他类型转为字符串
            else:
                return str(value)
        
        if not isinstance(result, dict):
            return _convert_value(result)
        
        serializable_result = {}
        for key, value in result.items():
            try:
                # 特殊处理已知的复杂对象类型
                if key == "operations" and isinstance(value, list):
                    # 转换EditOperation对象为字典
                    serializable_result[key] = [
                        {
                            "position": op.position if hasattr(op, 'position') else str(op),
                            "payload": _convert_value(op.payload) if hasattr(op, 'payload') else _convert_value(op)
                        } if hasattr(op, 'position') else _convert_value(op)
                        for op in value
                    ]
                elif key == "annotations" and isinstance(value, list):
                    # 转换DocumentAnnotation对象为字典
                    serializable_result[key] = [
                        {
                            "doc_id": ann.doc_id if hasattr(ann, 'doc_id') else str(ann),
                            "tags": ann.tags if hasattr(ann, 'tags') else [],
                            "confidence": ann.confidence if hasattr(ann, 'confidence') else 0.0
                        } if hasattr(ann, 'doc_id') else _convert_value(ann)
                        for ann in value
                    ]
                else:
                    # 使用通用转换方法
                    serializable_result[key] = _convert_value(value)
                    
            except Exception as e:
                print(f"Error serializing key '{key}' with value type {type(value)}: {e}")
                serializable_result[key] = str(value)
        
        return serializable_result
    
    def test_serialization(self, test_data: Any) -> bool:
        """测试数据是否可以成功序列化"""
        try:
            serializable_data = self._make_result_serializable(test_data)
            json.dumps(serializable_data, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"序列化测试失败: {e}")
            return False
    
    async def process_knowledge_base(
        self,
        kb_id: str,
        mode: SDTMMode,
        batch_size: int = 10,
        max_iterations: int = 100,
        auto_apply: bool = True,
        abnormal_doc_slots: int = 3,
        normal_doc_slots: int = 7,
        abnormal_doc_threshold: float = 3.0,
        enable_early_termination: bool = True
    ) -> Dict[str, Any]:
        """处理知识库 - 主要入口点"""
        
        try:
            # 获取知识库信息
            kb = self.kb_service.get_kb_by_id(kb_id)
            if not kb:
                raise ValueError(f"Knowledge base {kb_id} not found")
            
            # 获取当前统计信息
            stats = self.stats_service.get_kb_sdtm_stats(kb_id)
            
            # 获取待处理文档
            documents_to_process = self.stats_service.get_documents_to_process(kb_id, batch_size)
            
            if not documents_to_process:
                return {
                    "success": True,
                    "message": "没有需要处理的文档",
                    "operations": [],
                    "annotations": [],
                    "stats": stats
                }
            
            # 调用SDTM引擎处理文档
            response = await self.engine.process_documents(
                mode=mode,
                progress_metrics=stats.progress_metrics,
                quality_metrics=stats.quality_metrics,
                current_tag_dictionary=kb.tag_dictionary or {},
                documents_to_process=documents_to_process,
                abnormal_documents=stats.abnormal_documents
            )
            
            # 根据模式处理响应
            if mode == SDTMMode.EDIT:
                return await self._handle_edit_mode(kb_id, response, auto_apply)
            elif mode == SDTMMode.ANNOTATE:
                return await self._handle_annotate_mode(kb_id, response, auto_apply)
            elif mode == SDTMMode.SHADOW:
                return await self._handle_shadow_mode(kb_id, response)
            
        except Exception as e:
            return {
                "success": False,
                "message": f"处理失败: {str(e)}",
                "operations": [],
                "annotations": [],
                "error": str(e)
            }
    
    async def _handle_edit_mode(
        self, 
        kb_id: str, 
        response: SDTMEngineResponse, 
        auto_apply: bool = True
    ) -> Dict[str, Any]:
        """处理编辑模式"""
        
        kb = self.kb_service.get_kb_by_id(kb_id)
        current_dict = kb.tag_dictionary or {}
        
        # 预览编辑操作效果
        preview_dict = self.engine.preview_edit_operations(current_dict, response.operations)
        
        applied_operations = []
        if auto_apply and response.operations:
            # 检查引擎是否已经应用了操作
            if response.updated_dictionary is not None:
                # 使用引擎已经应用的字典
                try:
                    logger.info(f"使用引擎已更新的标签字典 (包含 {len(response.operations)} 个操作)")
                    logger.debug(f"更新前的字典: {current_dict}")
                    logger.debug(f"更新后的字典: {response.updated_dictionary}")
                    
                    # 更新知识库标签字典
                    from app.schemas.knowledge_base import TagDictionaryUpdate
                    tag_update = TagDictionaryUpdate(tag_dictionary=response.updated_dictionary)
                    
                    logger.info("开始保存标签字典到数据库...")
                    updated_kb = self.kb_service.update_tag_dictionary(kb_id, tag_update)
                    logger.info(f"标签字典已保存，更新时间: {updated_kb.last_tag_directory_update_time}")
                    
                    applied_operations = response.operations
                    
                except Exception as e:
                    logger.error(f"使用引擎更新字典时出错: {e}")
                    import traceback
                    logger.error(f"详细错误信息: {traceback.format_exc()}")
            else:
                # 回退到手动应用操作
                try:
                    logger.debug("手动应用编辑操作")
                    new_dict = self.engine.apply_edit_operations(current_dict, response.operations)
                    
                    # 更新知识库标签字典
                    from app.schemas.knowledge_base import TagDictionaryUpdate
                    tag_update = TagDictionaryUpdate(tag_dictionary=new_dict)
                    self.kb_service.update_tag_dictionary(kb_id, tag_update)
                    
                    applied_operations = response.operations
                    
                except Exception as e:
                    logger.error(f"手动应用编辑操作时出错: {e}")
        
        # 应用文档标注
        applied_annotations = []
        if auto_apply and response.annotations:
            applied_annotations = await self._apply_annotations(response.annotations)
        
        # 获取更新后的统计信息
        updated_stats = self.stats_service.get_kb_sdtm_stats(kb_id)
        
        return {
            "success": True,
            "message": f"编辑模式处理完成，应用了 {len(applied_operations)} 个操作，{len(applied_annotations)} 个标注",
            "operations": applied_operations,
            "annotations": applied_annotations,
            "preview_dictionary": preview_dict,
            "reasoning": response.reasoning,
            "stats": updated_stats
        }
    
    async def _handle_annotate_mode(
        self, 
        kb_id: str, 
        response: SDTMEngineResponse, 
        auto_apply: bool = True
    ) -> Dict[str, Any]:
        """处理标注模式"""
        
        applied_annotations = []
        if auto_apply and response.annotations:
            applied_annotations = await self._apply_annotations(response.annotations)
        
        # 在标注模式下，只应用少量必要的编辑操作
        applied_operations = []
        if auto_apply and response.operations:
            # 检查引擎是否已经应用了操作
            if response.updated_dictionary is not None:
                # 使用引擎已经应用的字典，但在标注模式下需要谨慎
                try:
                    logger.info(f"标注模式：使用引擎已更新的标签字典 (包含 {len(response.operations)} 个操作)")
                    
                    # 更新知识库标签字典
                    from app.schemas.knowledge_base import TagDictionaryUpdate
                    tag_update = TagDictionaryUpdate(tag_dictionary=response.updated_dictionary)
                    
                    logger.debug("标注模式：开始保存标签字典到数据库...")
                    updated_kb = self.kb_service.update_tag_dictionary(kb_id, tag_update)
                    logger.info(f"标注模式：标签字典已保存，更新时间: {updated_kb.last_tag_directory_update_time}")
                    
                    applied_operations = response.operations
                    
                except Exception as e:
                    logger.error(f"标注模式：使用引擎更新字典时出错: {e}")
                    import traceback
                    logger.error(f"标注模式：详细错误信息: {traceback.format_exc()}")
            else:
                # 回退到手动应用操作，只应用前3个操作，避免过度修改
                limited_operations = response.operations[:3]
                
                if limited_operations:
                    kb = self.kb_service.get_kb_by_id(kb_id)
                    current_dict = kb.tag_dictionary or {}
                    
                    try:
                        logger.debug(f"标注模式：手动应用有限的编辑操作 ({len(limited_operations)} 个)")
                        new_dict = self.engine.apply_edit_operations(current_dict, limited_operations)
                        
                        from app.schemas.knowledge_base import TagDictionaryUpdate
                        tag_update = TagDictionaryUpdate(tag_dictionary=new_dict)
                        self.kb_service.update_tag_dictionary(kb_id, tag_update)
                        
                        applied_operations = limited_operations
                        
                    except Exception as e:
                        logger.error(f"标注模式：手动应用有限编辑操作时出错: {e}")
        
        # 获取更新后的统计信息
        updated_stats = self.stats_service.get_kb_sdtm_stats(kb_id)
        
        return {
            "success": True,
            "message": f"标注模式处理完成，应用了 {len(applied_annotations)} 个标注，{len(applied_operations)} 个编辑操作",
            "operations": applied_operations,
            "annotations": applied_annotations,
            "reasoning": response.reasoning,
            "stats": updated_stats
        }
    
    async def _handle_shadow_mode(
        self, 
        kb_id: str, 
        response: SDTMEngineResponse
    ) -> Dict[str, Any]:
        """处理影子模式 - 用于监测语义漂移"""
        
        # 在影子模式下，不应用任何操作，只是监测和记录
        kb = self.kb_service.get_kb_by_id(kb_id)
        current_dict = kb.tag_dictionary or {}
        
        # 使用引擎预览的字典（如果有）或手动预览操作效果
        if response.updated_dictionary is not None:
            preview_dict = response.updated_dictionary
            logger.debug("影子模式：使用引擎预览的字典")
        else:
            preview_dict = self.engine.preview_edit_operations(current_dict, response.operations)
            logger.debug("影子模式：手动预览操作效果")
        
        # 计算语义漂移指标
        drift_metrics = self._calculate_semantic_drift(current_dict, preview_dict, response)
        
        # 记录影子模式操作（可以存储到日志或数据库）
        shadow_log = {
            "kb_id": kb_id,
            "timestamp": datetime.now().isoformat(),
            "operations": [op.dict() for op in response.operations],
            "annotations": [ann.dict() for ann in response.annotations],
            "drift_metrics": drift_metrics,
            "reasoning": response.reasoning
        }
        
        # 这里可以存储到监控系统或日志
        print(f"Shadow mode log: {json.dumps(shadow_log, ensure_ascii=False, indent=2)}")
        
        return {
            "success": True,
            "message": f"影子模式处理完成，检测到 {len(response.operations)} 个潜在编辑操作",
            "operations": response.operations,  # 不应用，只返回
            "annotations": response.annotations,  # 不应用，只返回
            "preview_dictionary": preview_dict,
            "drift_metrics": drift_metrics,
            "reasoning": response.reasoning,
            "shadow_log": shadow_log
        }
    
    def _calculate_semantic_drift(
        self, 
        current_dict: Dict[str, Any], 
        preview_dict: Dict[str, Any], 
        response: SDTMEngineResponse
    ) -> Dict[str, Any]:
        """计算语义漂移指标"""
        
        # 简单的漂移指标计算
        current_tags = self._flatten_dictionary(current_dict)
        preview_tags = self._flatten_dictionary(preview_dict)
        
        added_tags = set(preview_tags) - set(current_tags)
        removed_tags = set(current_tags) - set(preview_tags)
        
        return {
            "operations_count": len(response.operations),
            "annotations_count": len(response.annotations),
            "added_tags_count": len(added_tags),
            "removed_tags_count": len(removed_tags),
            "total_tags_before": len(current_tags),
            "total_tags_after": len(preview_tags),
            "drift_percentage": (len(added_tags) + len(removed_tags)) / max(len(current_tags), 1) * 100
        }
    
    def _flatten_dictionary(self, d: Dict[str, Any]) -> List[str]:
        """展平字典，获取所有叶子节点标签"""
        tags = []
        for key, value in d.items():
            if isinstance(value, dict):
                tags.extend(self._flatten_dictionary(value))
            elif isinstance(value, list):
                tags.extend(value)
            else:
                tags.append(key)
        return tags
    
    async def _apply_annotations(self, annotations: List[DocumentAnnotation]) -> List[DocumentAnnotation]:
        """应用文档标注 - 同时更新SQLite和Milvus记录"""
        applied_annotations = []
        
        for annotation in annotations:
            try:
                # 更新SQLite中的chunk标签
                chunk = self.chunk_repo.get_chunk_by_id(annotation.doc_id)
                if chunk:
                    # 更新chunk的标签字段
                    old_tags = chunk.tags
                    chunk.tags = json.dumps(annotation.tags, ensure_ascii=False)
                    self.db.commit()
                    
                    # 同时更新Milvus中的向量记录
                    try:
                        from app.repositories.milvus_repo import MilvusRepository
                        milvus_repo = MilvusRepository()
                        
                        # 检查是否有对应的向量记录
                        vector_exists = milvus_repo.check_vector_exists(chunk.kb_id, chunk.id)
                        
                        if vector_exists:
                            # 更新Milvus中的标签元数据
                            milvus_repo.update_vector_metadata(
                                kb_id=chunk.kb_id,
                                chunk_id=chunk.id,
                                metadata={
                                    "tags": annotation.tags,
                                    "last_updated": datetime.now().isoformat()
                                }
                            )
                            logger.debug(f"Updated vector metadata for chunk {chunk.id}")
                        else:
                            logger.warning(f"No vector found for chunk {chunk.id} in Milvus")
                            
                    except Exception as milvus_error:
                        logger.error(f"Error updating Milvus for chunk {chunk.id}: {milvus_error}")
                        # Milvus更新失败不应阻止SQLite更新成功的记录
                    
                    applied_annotations.append(annotation)
                    logger.debug(f"Successfully applied annotation to chunk {annotation.doc_id}: {old_tags} -> {annotation.tags}")
                else:
                    logger.warning(f"Chunk {annotation.doc_id} not found for annotation")
                    
            except Exception as e:
                logger.error(f"Error applying annotation to {annotation.doc_id}: {e}")
        
        return applied_annotations
    
    async def optimize_tag_dictionary(
        self, 
        kb_id: str, 
        batch_size: int = 10, 
        auto_apply: bool = False
    ) -> Dict[str, Any]:
        """优化标签字典 - 专门用于字典优化的接口"""
        
        return await self.process_knowledge_base(
            kb_id=kb_id,
            mode=SDTMMode.EDIT,
            batch_size=batch_size,
            auto_apply=auto_apply
        )
    
    async def batch_annotate_documents(
        self, 
        kb_id: str, 
        document_ids: List[str] = None,
        batch_size: int = 10
    ) -> Dict[str, Any]:
        """批量标注文档"""
        
        # 如果指定了文档ID，则只处理这些文档
        if document_ids:
            documents_to_process = []
            for doc_id in document_ids:
                chunk = self.chunk_repo.get_chunk_by_id(doc_id)
                if chunk:
                    try:
                        current_tags = []
                        if chunk.tags:
                            if isinstance(chunk.tags, str):
                                current_tags = json.loads(chunk.tags)
                            else:
                                current_tags = chunk.tags
                        
                        documents_to_process.append(DocumentInfo(
                            doc_id=chunk.id,
                            content=chunk.content,
                            current_tags=current_tags,
                            kb_id=kb_id,
                            chunk_index=chunk.chunk_index
                        ))
                    except (json.JSONDecodeError, TypeError):
                        documents_to_process.append(DocumentInfo(
                            doc_id=chunk.id,
                            content=chunk.content,
                            current_tags=[],
                            kb_id=kb_id,
                            chunk_index=chunk.chunk_index
                        ))
            
            # 直接处理指定的文档
            if documents_to_process:
                kb = self.kb_service.get_kb_by_id(kb_id)
                stats = self.stats_service.get_kb_sdtm_stats(kb_id)
                
                response = await self.engine.process_documents(
                    mode=SDTMMode.ANNOTATE,
                    progress_metrics=stats.progress_metrics,
                    quality_metrics=stats.quality_metrics,
                    current_tag_dictionary=kb.tag_dictionary or {},
                    documents_to_process=documents_to_process,
                    abnormal_documents=stats.abnormal_documents
                )
                
                # 应用标注
                applied_annotations = await self._apply_annotations(response.annotations)
                
                return {
                    "success": True,
                    "message": f"批量标注完成，处理了 {len(applied_annotations)} 个文档",
                    "annotations": applied_annotations,
                    "reasoning": response.reasoning,
                    "failed_documents": [doc_id for doc_id in document_ids 
                                       if doc_id not in [ann.doc_id for ann in applied_annotations]]
                }
        
        # 否则使用标准的标注模式
        return await self.process_knowledge_base(
            kb_id=kb_id,
            mode=SDTMMode.ANNOTATE,
            batch_size=batch_size
        )
    
    def get_kb_stats(self, kb_id: str) -> SDTMStats:
        """获取知识库SDTM统计信息"""
        return self.stats_service.get_kb_sdtm_stats(kb_id)
    
    def _verify_tag_dictionary_update(self, db: Session, kb_id: str, job_id: str):
        """验证标签字典是否确实被更新到数据库"""
        try:
            logger.debug("验证标签字典更新状态...")
            from app.models.knowledge_base import KnowledgeBase
            kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
            if kb:
                logger.debug(f"验证成功: 知识库 {kb_id} 已找到")
                logger.debug(f"   标签字典存在: {kb.tag_dictionary is not None}")
                if kb.tag_dictionary:
                    dict_size = len(str(kb.tag_dictionary))
                    logger.debug(f"   标签字典大小: {dict_size} 字符")
                    
                    # 显示字典的顶级结构
                    if isinstance(kb.tag_dictionary, dict):
                        top_keys = list(kb.tag_dictionary.keys())[:5]  # 显示前5个键
                        logger.debug(f"   顶级键: {top_keys}")
                else:
                    logger.warning("   标签字典为空")
                
                logger.debug(f"   最后更新时间: {kb.last_tag_directory_update_time}")
                
                if kb.last_tag_directory_update_time:
                    from datetime import datetime, timedelta
                    now = datetime.now()
                    time_diff = now - kb.last_tag_directory_update_time
                    if time_diff < timedelta(minutes=5):
                        logger.debug(f"   更新时间正常，距离现在 {time_diff.total_seconds():.1f} 秒")
                    else:
                        logger.warning(f"   更新时间较早，距离现在 {time_diff}")
                else:
                    logger.warning("   未记录更新时间")
            else:
                logger.error(f"验证失败: 知识库 {kb_id} 未找到")
        except Exception as e:
            logger.error(f"验证标签字典更新时出错: {e}")
            import traceback
            logger.error(f"验证错误详情: {traceback.format_exc()}") 