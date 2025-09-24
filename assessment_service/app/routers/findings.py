"""
API router for managing Assessment Findings directly.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from ..database import get_db
from .. import services, schemas

router = APIRouter(
    prefix="/findings",
    tags=["Findings"]
)

@router.get("/", response_model=List[schemas.AssessmentFindingResponse])
def list_findings(
    finding_ids: Optional[List[UUID]] = Query(None, description="List of finding IDs to filter by. If provided, session_id and job_id are ignored."),
    session_id: Optional[UUID] = Query(None, description="Filter findings by session ID"),
    job_id: Optional[UUID] = Query(None, description="Filter findings by job ID"),
    judgements: Optional[List[str]] = Query(None, description="List of judgements to filter by. If not provided, all non-null judgements are included."),
    db: Session = Depends(get_db)
):
    """
    List assessment findings with optional filtering.
    
    Filtering options:
    - finding_ids: List of specific finding IDs (mutually exclusive with session_id and job_id)
    - session_id: Filter by session ID
    - job_id: Filter by job ID
    - judgements: Filter by judgement values
    
    Note: finding_ids, session_id, and job_id are mutually exclusive.
    """
    # Validate mutually exclusive filters
    filter_count = sum([
        finding_ids is not None,
        session_id is not None,
        job_id is not None
    ])
    
    if filter_count > 1:
        raise HTTPException(
            status_code=400, 
            detail="Only one of finding_ids, session_id, or job_id can be specified"
        )
    
    # If finding_ids is provided, we only use that filter
    if finding_ids is not None:
        findings = services.get_findings_by_ids(db=db, finding_ids=finding_ids)
    else:
        # Use session_id or job_id filters
        findings = services.get_findings_by_filters(
            db=db, 
            session_id=session_id, 
            job_id=job_id, 
            judgements=judgements
        )
    
    return findings

@router.get("/{finding_id}", response_model=schemas.AssessmentFindingResponse)
def get_finding(finding_id: UUID, db: Session = Depends(get_db)):
    """
    Get details of a single assessment finding.
    """
    finding = services.get_finding_by_id(db=db, finding_id=finding_id)
    if finding is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    return finding