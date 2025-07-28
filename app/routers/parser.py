"""
解析器路由
文件: parser.py
创建时间: 2025-07-26
描述: 提供文档解析的API接口
"""

import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.kb_auth import get_kb_admin_or_owner, get_document_kb_access
from app.models.user import User
from app.models.knowledge_base import KnowledgeBase
from app.schemas.parser import (
    DocumentParseRequest, BatchParseRequest, ParseResponse,
    BatchParseResponse, ParseStatusResponse, ParseStatsResponse
)
from app.schemas.job import JobResponse
from app.services.fragment_parser_service import fragment_parser_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/parser", tags=["parser"])


@router.post("/kb/{kb_id}/parse", response_model=ParseResponse)
async def parse_document(
    kb_id: str = Path(..., description="知识库ID"),
    parse_request: DocumentParseRequest = ...,
    current_user: User = Depends(get_current_user),
    kb: KnowledgeBase = Depends(get_kb_admin_or_owner),
    db: Session = Depends(get_db)
):
    """解析单个文档生成Fragment（需要管理员权限）"""
    try:
        result = await fragment_parser_service.parse_document_fragments(
            db=db,
            kb_id=kb_id,
            document_id=parse_request.document_id,
            force_reparse=parse_request.force_reparse
        )

        # 获取准确的fragment统计信息
        parse_duration_ms = 0
        if result['status'] == 'success':
            fragment_stats = fragment_parser_service.get_document_fragment_stats(db, result['document_id'])
            total_fragments = fragment_stats.get('total_fragments', 0)
            text_fragments = fragment_stats.get('text_fragments', 0)
            screenshot_fragments = fragment_stats.get('screenshot_fragments', 0)
            figure_fragments = fragment_stats.get('figure_fragments', 0)

            # 尝试从解析结果中获取耗时信息
            if 'parse_duration_ms' in result:
                parse_duration_ms = result['parse_duration_ms']
        else:
            total_fragments = result.get('fragments_created', 0)
            text_fragments = 0
            screenshot_fragments = 0
            figure_fragments = 0

        return ParseResponse(
            document_id=result['document_id'],
            total_fragments=total_fragments,
            text_fragments=text_fragments,
            screenshot_fragments=screenshot_fragments,
            figure_fragments=figure_fragments,
            parse_duration_ms=parse_duration_ms,
            success=result['status'] == 'success',
            error_message=result.get('error') if result['status'] == 'error' else None
        )

    except Exception as e:
        logger.error(f"解析文档失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"解析失败: {str(e)}"
        )


@router.post("/kb/{kb_id}/batch-parse", response_model=JobResponse)
async def batch_parse_documents(
    kb_id: str = Path(..., description="知识库ID"),
    batch_request: BatchParseRequest = ...,
    current_user: User = Depends(get_current_user),
    kb: KnowledgeBase = Depends(get_kb_admin_or_owner),
    db: Session = Depends(get_db)
):
    """批量解析文档生成Fragment（基于任务队列，需要管理员权限）"""
    try:
        from app.services.unified_job_service import unified_job_service
        from app.models.job import Job, Task, JobType, TaskType, TargetType
        import uuid

        # 创建Job
        job = Job(
            id=str(uuid.uuid4()),
            kb_id=kb_id,
            job_type=JobType.BATCH_PARSE.value,
            total_tasks=len(batch_request.document_ids)
        )
        # 设置配置
        job.config_dict = {
            "force_reparse": batch_request.force_reparse,
            "max_concurrent": batch_request.max_concurrent
        }
        db.add(job)
        db.flush()  # 获取job.id

        # 创建Tasks
        tasks = []
        for document_id in batch_request.document_ids:
            task = Task(
                id=str(uuid.uuid4()),
                job_id=job.id,
                task_type=TaskType.PARSE_DOCUMENT.value,
                target_id=document_id,
                target_type=TargetType.DOCUMENT.value
            )
            # 设置任务配置
            task.config_dict = {
                "force_reparse": batch_request.force_reparse
            }
            tasks.append(task)
            db.add(task)

        db.commit()

        # 提交到任务队列
        await unified_job_service.submit_job(job, tasks, db)

        # 手动创建JobResponse以确保config字段正确序列化
        return JobResponse(
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
        )

    except Exception as e:
        logger.error(f"批量解析失败: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量解析失败: {str(e)}"
        )


@router.get("/document/{document_id}/status", response_model=ParseStatusResponse)
async def get_parse_status(
    document_id: str = Path(..., description="文档ID"),
    current_user: User = Depends(get_current_user),
    kb_id: str = Depends(get_document_kb_access),
    db: Session = Depends(get_db)
):
    """获取文档解析状态"""
    try:
        status_info = fragment_parser_service.get_parse_status(db, document_id)

        return ParseStatusResponse(
            document_id=document_id,
            status=status_info.get('status', 'unknown'),
            last_parsed_at=status_info.get('last_parsed_at'),
            fragment_count=status_info.get('fragment_count', 0),
            error_message=status_info.get('error_message')
        )

    except Exception as e:
        logger.error(f"获取解析状态失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取状态失败: {str(e)}"
        )


@router.get("/kb/{kb_id}/stats", response_model=ParseStatsResponse)
async def get_parse_stats(
    kb_id: str = Path(..., description="知识库ID"),
    current_user: User = Depends(get_current_user),
    kb: KnowledgeBase = Depends(get_kb_admin_or_owner),
    db: Session = Depends(get_db)
):
    """获取知识库解析统计信息"""
    try:
        stats = fragment_parser_service.get_kb_parse_stats(db, kb_id)

        return ParseStatsResponse(
            kb_id=kb_id,
            total_documents=stats.get('total_documents', 0),
            parsed_documents=stats.get('parsed_documents', 0),
            pending_documents=stats.get('pending_documents', 0),
            failed_documents=stats.get('failed_documents', 0),
            total_fragments=stats.get('total_fragments', 0),
            last_updated=stats.get('last_updated')
        )

    except Exception as e:
        logger.error(f"获取解析统计失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取统计失败: {str(e)}"
        )


@router.delete("/kb/{kb_id}/fragments/{document_id}")
async def delete_document_fragments(
    kb_id: str = Path(..., description="知识库ID"),
    document_id: str = Path(..., description="文档ID"),
    current_user: User = Depends(get_current_user),
    kb: KnowledgeBase = Depends(get_kb_admin_or_owner),
    db: Session = Depends(get_db)
):
    """删除文档的所有Fragment"""
    try:
        deleted_count = fragment_parser_service.delete_document_fragments(db, document_id)
        return {
            "kb_id": kb_id,
            "document_id": document_id,
            "deleted_fragments": deleted_count,
            "success": True
        }

    except Exception as e:
        logger.error(f"删除文档Fragment失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除失败: {str(e)}"
        )