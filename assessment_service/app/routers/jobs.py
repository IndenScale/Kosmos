"""
API router for managing Assessment Jobs.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Header
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from ..database import get_db
from .. import services, schemas

router = APIRouter(
    prefix="/jobs",
    tags=["Jobs"]
)

@router.post("/", response_model=schemas.JobCreateResponse, status_code=201)
def create_job(job: schemas.JobCreate, db: Session = Depends(get_db)):
    """
    Create a new assessment job.

    This will automatically populate the job with empty findings for every
    control item in the specified framework.
    """
    try:
        created_job, findings_count = services.create_job(db=db, job_create=job)
        return {
            "id": created_job.id,
            "name": created_job.name,
            "framework_id": created_job.framework_id,
            "status": created_job.status,
            "findings_created": findings_count,
        }
    except ValueError as e:
        # This happens if the framework_id is not found in the service
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/", response_model=List[schemas.JobSummaryResponse])
def list_jobs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    List all assessment jobs.
    """
    return services.get_jobs(db=db, skip=skip, limit=limit)

@router.get("/{job_id}", response_model=schemas.JobResponse)
def get_job(job_id: UUID, db: Session = Depends(get_db)):
    """
    Get details of a single assessment job, including all its findings.
    """
    db_job = services.get_job_by_id(db=db, job_id=job_id)
    if db_job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return db_job

@router.get("/{job_id}/sessions", response_model=List[schemas.SessionResponse])
def list_sessions_for_job(
    job_id: UUID,
    status: Optional[str] = Query(None, description="Filter sessions by status (e.g., 'COMPLETED', 'ABANDONED')."),
    db: Session = Depends(get_db)
):
    """
    List all assessment sessions associated with a specific job.
    Allows filtering by session status.
    """
    # First, check if the job exists to return a proper 404.
    if not services.get_job_by_id(db=db, job_id=job_id):
        raise HTTPException(status_code=404, detail="Job not found")
        
    sessions = services.get_sessions_for_job(db=db, job_id=job_id, status=status)
    return sessions

@router.get("/{job_id}/export", response_model=List[schemas.AssessmentFindingResponse])
def export_job_findings(
    job_id: UUID,
    judgements: Optional[List[str]] = Query(None, description="List of judgements to filter by. If not provided, all non-null judgements are included."),
    db: Session = Depends(get_db)
):
    """
    Export all findings for a specific job, with optional filtering.
    """
    # First, check if the job exists to return a proper 404.
    if not services.get_job_by_id(db=db, job_id=job_id):
        raise HTTPException(status_code=404, detail="Job not found")

    findings = services.export_findings_by_job_id(db=db, job_id=job_id, judgements=judgements)
    return findings


@router.delete("/", status_code=200)
def delete_jobs(
    payload: schemas.JobsDeleteRequest,
    db: Session = Depends(get_db)
):
    """
    Delete one or more jobs by their IDs.
    """
    if not payload.job_ids:
        raise HTTPException(status_code=400, detail="No job IDs provided.")
    
    deleted_count = services.delete_jobs_by_ids(db=db, job_ids=payload.job_ids)
    
    if deleted_count < len(payload.job_ids):
        return {"detail": f"Successfully deleted {deleted_count} job(s). Some requested jobs were not found."}

    return {"detail": f"Successfully deleted {deleted_count} job(s)."}

@router.get("/{job_id}/export/html", response_class=HTMLResponse)
def export_job_as_html(
    job_id: UUID,
    judgements: Optional[List[str]] = Query(None, description="List of judgements to filter by. If not provided, all non-null judgements are included."),
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None, description="User's KB token for credential delegation.")
):
    """
    Export a full report for a job as an HTML file, with optional judgement filtering.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")
    
    token = authorization.split("Bearer ")[1]
    
    html_content = services.generate_html_report(
        db=db, job_id=job_id, token=token, judgements=judgements
    )
    
    if html_content is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return HTMLResponse(content=html_content)
