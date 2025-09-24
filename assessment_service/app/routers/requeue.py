"""
API router for requeuing assessment jobs.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import requeue_service
from .. import schemas

router = APIRouter(
    prefix="/execute/job",
    tags=["Execution"]
)

@router.post("/{job_id}/requeue", response_model=schemas.RequeueSessionResponse, status_code=202)
def requeue_assessment_job(
    job_id: str,
    request: schemas.RequeueSessionRequest,
    db: Session = Depends(get_db)
):
    """
    基于session状态过滤器重新调度job的sessions。
    只重新调度指定状态的session，其他状态保持不变。
    """
    try:
        # 创建包含job_id的请求对象传递给service
        response = requeue_service.requeue_sessions_by_states(db=db, job_id=job_id, request=request)
        return response
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An internal error occurred: {e}")
