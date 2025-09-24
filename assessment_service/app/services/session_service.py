"""
Service layer for handling the business logic of Assessment Sessions.
"""
import os
import logging
import uuid
from uuid import UUID
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select
from typing import List, Optional, Any

from .. import models, schemas
from ..fsm import initialize_fsm
from . import job_service # Import the job_service to access the timeout logic
from typing import List, Optional, Any, Union

class SubmissionValidationError(ValueError):
    """Custom exception for submission validation errors."""
    pass

def create_session(db: Session, job_id: UUID, findings_batch: List[models.AssessmentFinding]) -> Optional[models.AssessmentSession]:
    """
    Creates a new assessment session for a given job with a specific batch of findings.
    """
    logging.info(f"Attempting to create session for job_id={job_id} with a batch of {len(findings_batch)} findings.")
    
    job = db.query(models.AssessmentJob).filter(models.AssessmentJob.id == job_id).first()
    if not job:
        raise ValueError(f"Job with id {job_id} not found.")

    # If the job is pending, this is the first action on it. Mark it as assessing.
    if job.status == 'PENDING':
        job.status = 'ASSESSING'
        db.add(job)

    if not findings_batch:
        logging.warning(f"No findings provided for job {job_id}. No session will be created.")
        return None

    # Read action limit from environment variable, with a default of 100
    try:
        action_limit = int(os.environ.get("ASSESSMENT_ACTION_LIMIT", 100))
    except (ValueError, TypeError):
        action_limit = 100

    db_session = models.AssessmentSession(
        job_id=job_id,
        status='READY_FOR_ASSESSMENT',
        action_limit=action_limit
    )
    db.add(db_session)
    
    # Assign the pre-fetched findings to the session
    db_session.findings.extend(findings_batch)
    
    db.flush() # Flush to get the db_session.id and persist relationships
    
    logging.info(f"Created new session with id={db_session.id} and assigned {len(db_session.findings)} findings.")
    
    # The commit is handled by the calling service function
    db.refresh(db_session)
    return db_session

def get_sessions(db: Session, job_id: Optional[UUID] = None, status: Optional[str] = None, session_ids: Optional[List[UUID]] = None, skip: int = 0, limit: int = 100) -> List[models.AssessmentSession]:
    """
    Retrieves a list of sessions with optional filters for job_id, status and session_ids.
    """
    query = db.query(models.AssessmentSession).options(selectinload(models.AssessmentSession.findings))

    if job_id:
        query = query.filter(models.AssessmentSession.job_id == job_id)
    
    if status:
        query = query.filter(models.AssessmentSession.status == status)
        
    if session_ids:
        query = query.filter(models.AssessmentSession.id.in_(session_ids))
        
    return query.offset(skip).limit(limit).all()

def update_session(db: Session, session_id: UUID, update_data: schemas.SessionUpdate) -> Optional[models.AssessmentSession]:
    """
    Updates an existing assessment session.
    """
    session = get_session_by_id(db, session_id)
    if not session:
        return None

    update_payload = update_data.dict(exclude_unset=True)
    
    for key, value in update_payload.items():
        setattr(session, key, value)
        
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

def start_assessment(db: Session, session_id: UUID) -> models.AssessmentSession:
    """
    Transitions a session from 'READY_FOR_ASSESSMENT' to 'ASSESSING_CONTROLS'.
    """
    session = get_session_by_id(db, session_id)
    if not session:
        raise ValueError("Session not found.")

    fsm = initialize_fsm(session)
    if not session.is_status_READY_FOR_ASSESSMENT():
         raise PermissionError(f"Cannot start assessment. Session is already in state '{session.status}'.")

    session.start_assessment()
    # The commit is handled by the calling scheduler.
    # db.commit()
    db.refresh(session)
    return session

def get_session_by_id(db: Session, session_id: UUID) -> Optional[models.AssessmentSession]:
    """
    Retrieves a session by its ID, eagerly loading related data needed for actions.
    """
    return (
        db.query(models.AssessmentSession)
        .options(
            selectinload(models.AssessmentSession.findings)
            .selectinload(models.AssessmentFinding.control_item_definition),
            selectinload(models.AssessmentSession.job)
            .selectinload(models.AssessmentJob.knowledge_spaces) # CORRECT FIX APPLIED HERE
        )
        .filter(models.AssessmentSession.id == session_id)
        .first()
    )



def submit_session_for_review(db: Session, session_id: UUID) -> models.AssessmentSession:
    """
    Transitions a session to 'SUBMITTED_FOR_REVIEW', marks the queue item
    as completed, and triggers the scheduler for the next job.
    """
    from . import execution_service # Avoid circular import

    session = get_session_by_id(db, session_id)
    if not session:
        raise ValueError("Session not found.")

    if session.status == 'ABANDONED':
        raise PermissionError("Cannot modify an abandoned session.")

    fsm = initialize_fsm(session)
    if not session.is_status_ASSESSING_CONTROLS():
        raise PermissionError(f"Cannot submit session. Session is in state '{session.status}'.")

    if session.submit_for_review():
        # The automated part is done, mark it as completed in the queue
        queue_item = db.query(models.ExecutionQueue).filter(models.ExecutionQueue.session_id == session_id).first()
        if queue_item:
            queue_item.status = 'COMPLETED'

        db.commit()
        db.refresh(session)

        # Now that this session is done, immediately try to schedule the next one for the same job
        execution_service.schedule_next_session(db, job_id=session.job_id)

        return session
    else:
        db.rollback()
        missing_judgement = [f.control_item_definition.display_id for f in session.findings if f.judgement is None]
        if missing_judgement:
            raise SubmissionValidationError(f"State transition failed. The following findings are missing a judgement: {', '.join(missing_judgement)}.")

        missing_evidence = [
            f.control_item_definition.display_id 
            for f in session.findings 
            if f.judgement and f.judgement in [schemas.JudgementEnum.CONFORMANT, schemas.JudgementEnum.PARTIALLY_CONFORMANT] and not f.evidences
        ]
        if missing_evidence:
            raise SubmissionValidationError(f"State transition failed. The following findings are judged '符合' or '部分符合' but lack evidence: {', '.join(missing_evidence)}.")
        
        raise SubmissionValidationError("State transition failed for an unknown reason.")

def complete_session_review(db: Session, session_id: UUID) -> models.AssessmentSession:
    """
    Transitions a session from 'SUBMITTED_FOR_REVIEW' to 'COMPLETED'.
    """
    session = get_session_by_id(db, session_id)
    if not session:
        raise ValueError("Session not found.")

    fsm = initialize_fsm(session)
    if not session.is_status_SUBMITTED_FOR_REVIEW():
        raise PermissionError(f"Cannot complete session. Session is in state '{session.status}'.")
    
    if session.complete_review():
        db.commit()
        db.refresh(session)
        return session
    else:
        db.rollback()
        raise RuntimeError("An unexpected error occurred during the 'complete_review' state transition.")

def reject_session_submission(db: Session, session_id: UUID, reason: str) -> models.AssessmentSession:
    """
    Transitions a session from 'SUBMITTED_FOR_REVIEW' back to 'ASSESSING_CONTROLS'.
    """
    session = get_session_by_id(db, session_id)
    if not session:
        raise ValueError("Session not found.")

    fsm = initialize_fsm(session)
    if not session.is_status_SUBMITTED_FOR_REVIEW():
        raise PermissionError(f"Cannot reject session. Session is in state '{session.status}'.")

    if session.reject_submission():
        db.commit()
        db.refresh(session)
        return session
    else:
        db.rollback()
        raise RuntimeError("An unexpected error occurred during the 'reject_submission' state transition.")


def merge_evidence_for_session(db: Session, session_id: UUID) -> None:
    """
    Automatically merge evidence for a given session that belongs to the same finding.
    Evidence is merged if they point to the same document and their line ranges overlap,
    are continuous, or have a distance less than 5 lines.
    """
    # Get all evidence for this session
    session = get_session_by_id(db, session_id)
    if not session:
        return
    
    # Get all findings for this session
    findings = session.findings
    
    # For each finding, merge its evidence
    for finding in findings:
        # Get all evidence for this finding
        evidence_list = finding.evidences
        
        if len(evidence_list) < 2:
            continue  # No need to merge if less than 2 evidence
        
        # Group evidence by document ID
        evidence_by_doc = {}
        for evidence in evidence_list:
            doc_id = evidence.doc_id
            if doc_id not in evidence_by_doc:
                evidence_by_doc[doc_id] = []
            evidence_by_doc[doc_id].append(evidence)
        
        # For each document, merge evidence
        for doc_id, evidences in evidence_by_doc.items():
            if len(evidences) < 2:
                continue  # No need to merge if less than 2 evidence for this document
                
            # Sort evidence by start line
            evidences.sort(key=lambda x: x.start_line)
            
            # Merge overlapping or adjacent evidence
            merged_evidences = []
            current_evidence = evidences[0]
            
            for i in range(1, len(evidences)):
                next_evidence = evidences[i]
                
                # Check if evidence ranges are overlapping, adjacent, or within 5 lines
                if (current_evidence.end_line >= next_evidence.start_line or 
                    next_evidence.start_line - current_evidence.end_line <= 5):
                    # Merge evidence
                    current_evidence.end_line = max(current_evidence.end_line, next_evidence.end_line)
                else:
                    # Add current evidence to merged list and start new evidence
                    merged_evidences.append(current_evidence)
                    current_evidence = next_evidence
            
            # Add the last evidence
            merged_evidences.append(current_evidence)
            
            # Update database with merged evidence
            # First, delete all old evidence for this finding
            db.query(models.Evidence).filter(models.Evidence.finding_id == finding.id).delete()
            
            # Add merged evidence
            for evidence in merged_evidences:
                new_evidence = models.Evidence(
                    id=str(uuid.UUID()),
                    finding_id=finding.id,
                    doc_id=evidence.doc_id,
                    start_line=evidence.start_line,
                    end_line=evidence.end_line,
                    created_at=evidence.created_at
                )
                db.add(new_evidence)
            
            db.flush()