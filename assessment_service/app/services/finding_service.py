"""
Service layer for handling business logic related to Assessment Findings.
"""
import jinja2
import base64
from sqlalchemy import func, Interval, or_, and_
from sqlalchemy.orm import Session, selectinload
from typing import List, Optional
from datetime import datetime, timedelta
from uuid import UUID

from .. import models, schemas, kosmos_client
from ..fsm import initialize_fsm

def get_findings_by_ids(db: Session, finding_ids: List[UUID]) -> List[models.AssessmentFinding]:
    """
    Retrieve findings by a list of IDs.
    """
    return db.query(models.AssessmentFinding).filter(
        models.AssessmentFinding.id.in_(finding_ids)
    ).all()

def get_findings_by_filters(
    db: Session, 
    session_id: Optional[UUID] = None, 
    job_id: Optional[UUID] = None, 
    judgements: Optional[List[str]] = None
) -> List[models.AssessmentFinding]:
    """
    Retrieve findings with optional filtering by session_id, job_id, and judgements.
    """
    query = db.query(models.AssessmentFinding)
    
    # Apply session_id filter if provided
    if session_id is not None:
        query = query.filter(models.AssessmentFinding.session_id == session_id)
    
    # Apply job_id filter if provided
    if job_id is not None:
        query = query.filter(models.AssessmentFinding.job_id == job_id)
    
    # Apply judgements filter if provided
    if judgements is not None:
        if judgements:
            query = query.filter(models.AssessmentFinding.judgement.in_(judgements))
        else:
            # If empty list is provided, return no results
            return []
    else:
        # If no judgements filter is provided, only return findings with non-null judgements
        query = query.filter(models.AssessmentFinding.judgement.isnot(None))
    
    return query.all()

def get_finding_by_id(db: Session, finding_id: UUID) -> Optional[models.AssessmentFinding]:
    """
    Retrieve a single finding by its ID.
    """
    return db.query(models.AssessmentFinding).filter(
        models.AssessmentFinding.id == finding_id
    ).first()