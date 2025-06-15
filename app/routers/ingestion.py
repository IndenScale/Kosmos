from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.db.database import get_db
from app.models.user import User
from app.dependencies.auth import get_current_user
from app.dependencies.kb_auth import get_kb_admin_or_owner
from app.services.ingestion_service import IngestionService
from app.schemas.ingestion import IngestionJobResponse, IngestionJobListResponse

router = APIRouter(prefix="/api/v1", tags=["ingestion"])

@router.post("/kbs/{kb_id}/documents/{document_id}/ingest", response_model=IngestionJobResponse, status_code=status.HTTP_202_ACCEPTED)
def start_ingestion(
    kb_id: str,
    document_id: str,
    current_user: User = Depends(get_current_user),
    kb_member = Depends(get_kb_admin_or_owner),
    db: Session = Depends(get_db)
):
    """Start Ingestion - 启动文档摄入任务"""
    ingestion_service = IngestionService(db)

    try:
        # 处理异步方法调用
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        job_id = loop.run_until_complete(ingestion_service.start_ingestion_job(kb_id, document_id, current_user.id))
        job = ingestion_service.get_job_status(job_id)

        loop.close()
        return IngestionJobResponse.from_orm(job)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/jobs/{job_id}", response_model=IngestionJobResponse)
def get_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取摄入任务状态"""
    ingestion_service = IngestionService(db)
    job = ingestion_service.get_job_status(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")

    return IngestionJobResponse.from_orm(job)

@router.get("/kbs/{kb_id}/jobs", response_model=IngestionJobListResponse)
def list_kb_jobs(
    kb_id: str,
    current_user: User = Depends(get_current_user),
    kb_member = Depends(get_kb_admin_or_owner),
    db: Session = Depends(get_db)
):
    """List Kb Jobs - 列出知识库的所有摄入任务"""
    ingestion_service = IngestionService(db)
    jobs = ingestion_service.get_kb_jobs(kb_id)

    return IngestionJobListResponse(
        jobs=[IngestionJobResponse.from_orm(job) for job in jobs],
        total=len(jobs)
    )

@router.get("/kbs/{kb_id}/job-statuses", response_model=IngestionJobListResponse)
def get_document_job_statuses(
    kb_id: str,
    current_user: User = Depends(get_current_user),
    kb_member = Depends(get_kb_admin_or_owner),
    db: Session = Depends(get_db)
):
    """Get Document Job Statuses - 获取文档任务状态列表"""
    ingestion_service = IngestionService(db)
    jobs = ingestion_service.get_kb_jobs(kb_id)  # 使用现有的方法

    return IngestionJobListResponse(
        jobs=[IngestionJobResponse.from_orm(job) for job in jobs],
        total=len(jobs)
    )

@router.get("/queue/stats")
def get_queue_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)  # 添加 db 参数
):
    """Get Queue Stats - 获取队列统计信息"""
    ingestion_service = IngestionService(db)  # 传递 db 参数
    stats = ingestion_service.get_queue_stats()

    return {
        "pending_jobs": stats.get("pending", 0),
        "running_jobs": stats.get("running", 0),
        "completed_jobs": stats.get("completed", 0),
        "failed_jobs": stats.get("failed", 0),
        "total_jobs": stats.get("total", 0)
    }

@router.post("/kbs/{kb_id}/documents/{document_id}/reingest", response_model=IngestionJobResponse, status_code=status.HTTP_202_ACCEPTED)
def reingest_document(
    kb_id: str,
    document_id: str,
    current_user: User = Depends(get_current_user),
    kb_member = Depends(get_kb_admin_or_owner),
    db: Session = Depends(get_db)
):
    """Reingest Document - 重新摄入文档"""
    ingestion_service = IngestionService(db)

    try:
        # 先删除现有索引，然后重新摄入
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # 删除现有索引
        loop.run_until_complete(ingestion_service.delete_document_index(kb_id, document_id))

        # 重新开始摄入
        job_id = loop.run_until_complete(ingestion_service.start_ingestion_job(kb_id, document_id, current_user.id))
        job = ingestion_service.get_job_status(job_id)

        loop.close()
        return IngestionJobResponse.from_orm(job)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))