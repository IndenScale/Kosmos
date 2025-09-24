"""
Service functions for requeuing assessment jobs.
支持基于状态列表的精确重新调度。
"""
import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session, selectinload

from .. import models, schemas
from .execution_service import schedule_next_session, AgentDispatchError

def requeue_sessions_by_states(db: Session, job_id: str, request: schemas.RequeueSessionRequest) -> schemas.RequeueSessionResponse:
    """
    基于目标状态列表重新调度session的核心逻辑
    """
    # 处理默认值 - 如果未指定目标状态，使用默认的可重新调度状态
    target_states = request.target_states or [
        schemas.SessionStatus.READY_FOR_ASSESSMENT,
        schemas.SessionStatus.ASSESSING_CONTROLS,
        schemas.SessionStatus.SUBMITTED_FOR_REVIEW
    ]
    
    logging.info(f"开始基于状态列表重新调度session，job_id={job_id}, target_states={target_states}")
    
    # 获取job信息
    job = db.query(models.AssessmentJob).options(
        selectinload(models.AssessmentJob.sessions),
        selectinload(models.AssessmentJob.findings)
    ).filter(models.AssessmentJob.id == job_id).first()
    
    if not job:
        raise ValueError(f"Job with id {job_id} not found.")
    
    # 获取该job的所有session
    all_sessions = db.query(models.AssessmentSession).filter(
        models.AssessmentSession.job_id == job_id
    ).all()
    
    if not all_sessions:
        return schemas.RequeueSessionResponse(
            status="no_action",
            job_id=job_id,
            total_sessions_processed=0,
            sessions_requeued=0,
            sessions_skipped=0,
            state_breakdown={},
            target_states=target_states,
            message="该job没有任何session需要处理"
        )
    
    # 统计各状态session数量
    state_stats = {}
    target_state_set = set(target_states)
    
    for session in all_sessions:
        state = session.status
        if state not in state_stats:
            state_stats[state] = {"total": 0, "requeued": 0, "skipped": 0}
        state_stats[state]["total"] += 1
    
    # 清理现有队列项
    existing_queue_items = db.query(models.ExecutionQueue).filter(
        models.ExecutionQueue.job_id == job_id
    ).all()
    
    for item in existing_queue_items:
        db.delete(item)
    
    logging.info(f"清理了 {len(existing_queue_items)} 个现有队列项")
    
    # 处理session重新入队
    sessions_requeued = 0
    sessions_processed = 0
    
    try:
        for session in all_sessions:
            sessions_processed += 1
            current_state = session.status
            
            # 检查当前session状态是否在目标列表中
            if current_state in target_state_set:
                # 重置session状态
                session.status = schemas.SessionStatus.READY_FOR_ASSESSMENT
                session.action_count = 0
                session.error_count = 0
                session.warning_count = 0
                
                # 创建执行队列条目，包含新的认证和提示词配置
                execution_config = {
                    "agent": request.agent,
                    "session_batch_size": request.session_batch_size,
                    "openai_base_url": request.openai_base_url,
                    "openai_api_key": request.openai_api_key,
                    "openai_model": request.openai_model,
                    "kosmos_username": request.kosmos_username,
                    "kosmos_password": request.kosmos_password,
                    "agent_prompt": request.agent_prompt
                }
                
                queue_entry = models.ExecutionQueue(
                    session_id=session.id,
                    job_id=session.job_id,
                    status="PENDING",
                    execution_config=execution_config
                )
                db.add(queue_entry)
                
                state_stats[current_state]["requeued"] += 1
                sessions_requeued += 1
                logging.info(f"重新入队session {session.id}，原状态: {current_state}")
            else:
                state_stats[current_state]["skipped"] += 1
                logging.info(f"跳过session {session.id}，状态: {current_state} 不在目标列表中")
        
        db.commit()
        
        # 触发调度下一个session
        if sessions_requeued > 0:
            logging.info(f"已重新入队 {sessions_requeued} 个session。周期性调度器将处理它们。")
        
        # 确定最终状态
        if sessions_requeued == 0:
            final_status = "no_action"
            message = f"没有符合目标状态 {target_states} 的session需要重新调度"
        elif sessions_requeued == sessions_processed:
            final_status = "success"
            message = f"成功重新调度所有 {sessions_requeued} 个session"
        else:
            final_status = "partial"
            message = f"部分成功：重新调度 {sessions_requeued} 个session，跳过 {sessions_processed - sessions_requeued} 个"
        
        return schemas.RequeueSessionResponse(
            status=final_status,
            job_id=job_id,
            total_sessions_processed=sessions_processed,
            sessions_requeued=sessions_requeued,
            sessions_skipped=sessions_processed - sessions_requeued,
            state_breakdown=state_stats,
            target_states=target_states,
            message=message
        )
        
    except Exception as e:
        db.rollback()
        logging.error(f"重新调度session时出错: {e}")
        raise
