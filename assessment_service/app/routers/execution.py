"""
API router for dispatching and managing assessment executions.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import execution_service
from .. import schemas

router = APIRouter(
    prefix="/execute",
    tags=["Execution"]
)

@router.post("/session", response_model=schemas.SessionExecutionResponse, status_code=202)
def execute_assessment_session(
    request: schemas.SessionExecutionRequest,
    db: Session = Depends(get_db)
):
    """
    Dispatches an agent to start working on an assessment session for a given job.
    
    This endpoint accepts a job ID and knowledge space ID, constructs the
    appropriate agent command, and launches it as a background process.
    """
    try:
        response = execution_service.dispatch_session_agent(db=db, request=request)
        if response.status == "error":
            raise HTTPException(status_code=500, detail=response.command)
        return response
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An internal error occurred: {e}")

@router.post("/job/{job_id}", response_model=schemas.JobExecutionResponse, status_code=202)
def execute_assessment_job(
    job_id: str,
    request: schemas.JobExecutionRequest,
    db: Session = Depends(get_db)
):
    """
    Automatically creates and queues all sessions for a given assessment job.
    
    This endpoint calculates the required sessions based on the batch size,
    creates them, adds them to the execution queue, and triggers the scheduler
    to start processing the first session.
    """
    try:
        response = execution_service.enqueue_job_sessions(db=db, job_id=job_id, request=request)
        return response
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=409, detail=str(e)) # 409 Conflict is suitable for "already enqueued"
    except execution_service.AgentDispatchError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An internal error occurred: {e}")
