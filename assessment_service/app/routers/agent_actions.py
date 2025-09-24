"""
API router for agent actions within an assessment session.
All endpoints under this router require the session to be in 'ASSESSING_CONTROLS' state
and respect the session's action limits.
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import Any, Optional
from uuid import UUID

from ..database import get_db
from ..services import agent_service
from .. import schemas

router = APIRouter(
    prefix="/sessions/{session_id}/agent",
    tags=["Agent Workflow"]
)

# --- Endpoints ---

@router.post("/search", summary="Perform a search in the knowledge space")
def agent_search(
    session_id: UUID, 
    request: schemas.SearchActionRequest, 
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None)
) -> Any:
    """Performs a search query within the session's target knowledge space."""
    try:
        return agent_service.perform_agent_search(
            db=db, 
            session_id=session_id, 
            request=request,
            token=authorization
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error communicating with backend service: {e}")

@router.post("/read", summary="Read content from a document or bookmark")
def agent_read(
    session_id: UUID, 
    request: schemas.ReadActionRequest, 
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None)
) -> Any:
    """Reads content from a document or bookmark in the session's knowledge space."""
    try:
        return agent_service.perform_agent_read(
            db=db,
            session_id=session_id,
            doc_ref=request.doc_ref,
            start=request.start_line,
            end=request.end_line,
            token=authorization
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error communicating with backend service: {e}")

@router.post("/grep", summary="Perform a regex search across documents or a knowledge space")
def agent_grep(
    session_id: UUID,
    request: schemas.MultiGrepActionRequest,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None)
) -> Any:
    """Performs a regex search within the session's knowledge space context."""
    print(f"[DEBUG] agent_grep路由 - session_id: {session_id}, authorization: {authorization[:20] if authorization else None}...")
    print(f"[DEBUG] agent_grep路由 - request: {request}")
    try:
        return agent_service.perform_agent_grep(
            db=db,
            session_id=session_id,
            request=request,
            token=authorization
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        print(f"[DEBUG] agent_grep路由 - 异常: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=502, detail=f"Error communicating with backend service: {e}")

@router.post("/findings/{finding_id}/evidence", response_model=schemas.EvidenceResponse, status_code=201)
def add_evidence(session_id: UUID, finding_id: UUID, evidence: schemas.EvidenceCreate, db: Session = Depends(get_db)):
    """Add a piece of evidence to a specific finding."""
    try:
        return agent_service.add_evidence(db=db, session_id=session_id, finding_id=finding_id, evidence=evidence)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

@router.patch("/findings/{finding_id}", response_model=schemas.AssessmentFindingResponse)
def update_finding(session_id: UUID, finding_id: UUID, finding_update: schemas.AssessmentFindingUpdate, db: Session = Depends(get_db)):
    """Update a finding with a judgement and comments."""
    try:
        return agent_service.update_finding(db=db, session_id=session_id, finding_id=finding_id, finding_update=finding_update)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
