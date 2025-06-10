from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.db.database import get_db
from app.models.user import User
from app.dependencies.auth import get_current_user
from app.dependencies.kb_auth import get_kb_admin_or_owner
from app.services.ingestion_service import IngestionService
from app.schemas.ingestion import IngestionJobResponse, IngestionJobListResponse, QueueStatsResponse

router = APIRouter(prefix="/api/v1", tags=["ingestion"])

@router.post("/kbs/{kb_id}/documents/{document_id}/ingest", response_model=IngestionJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_ingestion(
    kb_id: str,
    document_id: str,
    current_user: User = Depends(get_current_user),
    kb_member = Depends(get_kb_admin_or_owner),
    db: Session = Depends(get_db)
):
    """启动文档摄入任务（异步）"""
    ingestion_service = IngestionService(db)

    try:
        job_id = await ingestion_service.start_ingestion_job(kb_id, document_id, current_user.id)
        job = ingestion_service.get_job_status(job_id)
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
    """列出知识库的所有摄入任务"""
    ingestion_service = IngestionService(db)
    jobs = ingestion_service.get_kb_jobs(kb_id)

    return IngestionJobListResponse(
        jobs=[IngestionJobResponse.from_orm(job) for job in jobs],
        total=len(jobs)
    )

@router.get("/queue/stats", response_model=QueueStatsResponse)
def get_queue_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取队列统计信息"""
    ingestion_service = IngestionService(db)
    stats = ingestion_service.get_queue_stats()
    return QueueStatsResponse(**stats)

@router.post("/api/v1/kbs/{kb_id}/documents/{document_id}/reindex")
async def reindex_document(
    kb_id: str,
    document_id: str,
    current_user: User = Depends(get_current_user),
    kb_member = Depends(get_kb_admin_or_owner),
    db: Session = Depends(get_db)
):
    """重新索引文档（删除原有索引后重新建立）"""
    ingestion_service = IngestionService(db)
    
    # 删除原有索引
    await ingestion_service.delete_document_index(kb_id, document_id)
    
    # 重新开始索引任务
    job = await ingestion_service.start_ingestion_job(kb_id, document_id)
    
    return {"job_id": job.id, "status": "started"}