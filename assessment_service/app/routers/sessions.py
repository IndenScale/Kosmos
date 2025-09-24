"""
API router for managing Assessment Sessions.
"""
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from transitions import MachineError
from uuid import UUID
from typing import List

from ..database import get_db
from .. import services, schemas

router = APIRouter(
    tags=["Sessions"]
)

@router.post("/jobs/{job_id}/sessions", response_model=schemas.SessionResponse, status_code=201)
def create_session_for_job(job_id: UUID, session_create: schemas.SessionCreate, db: Session = Depends(get_db)):
    """
    Creates a new assessment session for a job in the 'READY_FOR_ASSESSMENT' state.
    
    This fetches a batch of pending findings and assigns them to the new session,
    which acts as a "work contract" for an agent.
    """
    try:
        # Manually fetch a batch of findings for the new session
        pending_findings = (
            db.query(models.AssessmentFinding)
            .filter(
                models.AssessmentFinding.job_id == job_id,
                models.AssessmentFinding.session_id.is_(None)
            )
            .order_by(models.AssessmentFinding.id)
            .limit(session_create.batch_size)
            .all()
        )

        if not pending_findings:
            raise HTTPException(status_code=200, detail="No pending findings found for this job. The job is likely complete.")

        session = services.create_session(db=db, job_id=job_id, findings_batch=pending_findings)
        db.commit() # Commit the transaction for the manually created session
        db.refresh(session)
        return session
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/sessions/{session_id}/start", response_model=schemas.SessionResponse)
def start_session(session_id: UUID, db: Session = Depends(get_db)):
    """
    Starts an assessment session, moving it from 'READY' to 'ASSESSING'.
    """
    try:
        return services.start_assessment(db=db, session_id=session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=409, detail=str(e)) # 409 Conflict for wrong state

@router.get("/sessions/{session_id}", response_model=schemas.SessionResponse)
def get_session(session_id: UUID, db: Session = Depends(get_db)):
    """
    Get details of a single assessment session, including its findings.
    """
    db_session = services.get_session_by_id(db=db, session_id=session_id)
    if db_session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return db_session

@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: UUID, db: Session = Depends(get_db)):
    """
    Deletes a session and resets its findings back to the unassigned pool.
    This is a manual intervention tool for clearing stuck or erroneous sessions.
    """
    try:
        services.delete_session_and_reset_findings(db=db, session_id=session_id)
        return Response(status_code=204)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/sessions/", response_model=list[schemas.SessionSummaryResponse])
def list_sessions(
    job_id: UUID = None,
    status: str = None,
    session_ids: List[UUID] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    List sessions with optional filters.
    """
    sessions = services.get_sessions(db, job_id=job_id, status=status, session_ids=session_ids, skip=skip, limit=limit)
    return sessions

@router.get("/sessions/{session_id}", response_model=schemas.SessionResponse)
def get_session_by_id(session_id: UUID, db: Session = Depends(get_db)):
    """
    Get details of a single assessment session by its ID.
    """
    session = services.get_session_by_id(db=db, session_id=session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.put("/sessions/{session_id}", response_model=schemas.SessionResponse)
def update_session_details(session_id: UUID, session_update: schemas.SessionUpdate, db: Session = Depends(get_db)):
    """
    Update details of a specific session, such as limits.
    """
    updated_session = services.update_session(db=db, session_id=session_id, update_data=session_update)
    if updated_session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return updated_session

@router.post("/sessions/{session_id}/submit", response_model=schemas.SessionResponse)
def submit_session(session_id: UUID, db: Session = Depends(get_db)):
    """
    Submits a session for review, moving it to 'SUBMITTED_FOR_REVIEW'.
    Requires all findings in the session to have a judgement.
    """
    try:
        return services.submit_session_for_review(db=db, session_id=session_id)
    except services.SubmissionValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        # Catches "not found"
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=409, detail=str(e))

@router.post("/sessions/{session_id}/complete", response_model=schemas.SessionResponse)
def complete_session(session_id: UUID, db: Session = Depends(get_db)):
    """
    Finalizes a session, moving it to 'COMPLETED'.
    """
    try:
        return services.complete_session_review(db=db, session_id=session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=409, detail=str(e))

@router.post("/sessions/{session_id}/reject", response_model=schemas.SessionResponse)
def reject_session(session_id: UUID, rejection_details: schemas.SessionRejectRequest, db: Session = Depends(get_db)):
    """
    Rejects a submitted session, returning it to the 'ASSESSING_CONTROLS' state for rework.
    """
    try:
        return services.reject_session_submission(db=db, session_id=session_id, reason=rejection_details.reason)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
