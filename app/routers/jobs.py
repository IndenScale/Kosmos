"""
统一任务管理路由
文件: jobs.py
创建时间: 2025-07-26
描述: 提供统一任务系统的查询、管理和可观测性功能
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.db.database import get_db
from app.models.job import JobType, JobStatus
from app.schemas.job import (
    JobResponse, JobDetailResponse, JobListResponse,
    JobStatsResponse, QueueStatsResponse
)
from app.services.unified_job_service import unified_job_service
from app.dependencies.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/v1/jobs", tags=["任务管理"])


@router.get("/", response_model=JobListResponse)
async def list_jobs(
    kb_id: Optional[str] = Query(None, description="知识库ID"),
    job_type: Optional[JobType] = Query(None, description="任务类型"),
    status: Optional[JobStatus] = Query(None, description="任务状态"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取任务列表"""
    return unified_job_service.list_jobs(
        kb_id=kb_id,
        job_type=job_type,
        status=status,
        page=page,
        page_size=page_size,
        db=db
    )


@router.get("/{job_id}", response_model=JobDetailResponse)
async def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取任务详情"""
    job = unified_job_service.get_job(job_id, db)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job


@router.get("/stats/jobs", response_model=JobStatsResponse)
async def get_job_stats(
    kb_id: Optional[str] = Query(None, description="知识库ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取任务统计"""
    return unified_job_service.get_job_stats(kb_id=kb_id, db=db)


@router.get("/stats/queue", response_model=QueueStatsResponse)
async def get_queue_stats(
    current_user: User = Depends(get_current_user)
):
    """获取队列统计"""
    return unified_job_service.get_queue_stats()


@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """取消任务"""
    # TODO: 实现任务取消逻辑
    raise HTTPException(status_code=501, detail="功能暂未实现")


@router.post("/{job_id}/retry")
async def retry_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """重试任务"""
    success = await unified_job_service.retry_job(job_id, db)
    if not success:
        raise HTTPException(status_code=400, detail="任务重试失败")
    return {"message": "任务重试成功"}