"""
Service layer for handling agent actions within an assessment session.
"""
import json
import decimal
from uuid import UUID
from sqlalchemy.orm import Session
from typing import Optional, Any

from .. import models, schemas, kosmos_client
from ..fsm import initialize_fsm
from .session_service import get_session_by_id

# --- Helper Classes ---

class CustomJsonEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle UUID and Decimal types for logging."""
    def default(self, obj):
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        return super().default(obj)

# --- Agent Action Services ---

def _get_session_and_validate_for_action(db: Session, session_id: UUID) -> models.AssessmentSession:
    """Helper to get session, check state and action limits."""
    session = get_session_by_id(db, session_id)
    if not session:
        raise ValueError("Session not found.")
    
    if session.status == 'ABANDONED':
        raise PermissionError("Cannot perform actions on an abandoned session.")
    
    # 如果会话处于READY_FOR_ASSESSMENT状态，自动转换为ASSESSING_CONTROLS
    if session.status == 'READY_FOR_ASSESSMENT':
        fsm = initialize_fsm(session)
        print(f"[DEBUG] FSM初始化完成，当前状态: {session.status}")
        print(f"[DEBUG] FSM对象: {fsm}")
        print(f"[DEBUG] session对象方法: {dir(session)}")
        
        # 尝试调用正确的方法
        if hasattr(session, 'start_assessment'):
            session.start_assessment()
            db.commit()
            print(f"会话 {session_id} 状态已自动从 READY_FOR_ASSESSMENT 转换为 ASSESSING_CONTROLS")
        else:
            print(f"[ERROR] session对象没有start_assessment方法")
            # 手动更新状态作为备选方案
            session.status = 'ASSESSING_CONTROLS'
            db.commit()
            print(f"会话 {session_id} 状态已手动从 READY_FOR_ASSESSMENT 转换为 ASSESSING_CONTROLS")
    
    fsm = initialize_fsm(session)
    if not session.is_status_ASSESSING_CONTROLS():
        raise PermissionError(f"Cannot perform actions in state '{session.status}'.")
        
    if session.action_count >= session.action_limit:
        session.abandon_session()
        db.commit()
        raise PermissionError(f"Action limit exceeded for this session ({session.action_count}/{session.action_limit}). Session has been abandoned.")
        
    return session

def _get_target_ks_id(session: models.AssessmentSession) -> UUID:
    """Finds the target knowledge space ID from a session's pre-loaded job."""
    if not session.job or not session.job.knowledge_spaces:
        raise ValueError(f"No knowledge space links found for job {session.job_id}.")

    first_link = session.job.knowledge_spaces[0]
    return UUID(first_link.ks_id)

def perform_agent_search(db: Session, session_id: UUID, request: schemas.SearchActionRequest, token: Optional[str]) -> Any:
    """Logs and executes a search query via the Kosmos client."""
    session = _get_session_and_validate_for_action(db, session_id)
    target_ks_id = _get_target_ks_id(session)
    
    # Log all parameters for audit purposes
    log_params = request.dict()
    log_entry = models.ActionLog(session_id=session_id, action_type="search", parameters=log_params)
    db.add(log_entry)
    
    session.action_count += 1
    
    search_results = kosmos_client.search_in_kosmos(
        ks_id=target_ks_id,
        query=request.query,
        top_k=request.top_k,
        token=token,
        doc_ids_include=request.doc_ids_include,
        doc_ids_exclude=request.doc_ids_exclude,
        filename_contains=request.filename_contains,
        filename_does_not_contain=request.filename_does_not_contain,
        extensions_include=request.extensions_include,
        extensions_exclude=request.extensions_exclude,
        keywords_include_all=request.keywords_include_all,
        keywords_exclude_any=request.keywords_exclude_any,
        boosters=request.boosters
    )
    
    log_entry.result_summary = {"hits": len(search_results.get("results", []))}
    
    db.commit()
    return search_results

def perform_agent_read(db: Session, session_id: UUID, doc_ref: str, start: Optional[int], end: Optional[int], token: Optional[str]) -> Any:
    """Logs and executes a read request via the Kosmos client."""
    session = _get_session_and_validate_for_action(db, session_id)
    target_ks_id = _get_target_ks_id(session)

    parameters = {"doc_ref": doc_ref, "start": start, "end": end}
    log_entry = models.ActionLog(session_id=session_id, action_type="read", parameters=parameters)
    db.add(log_entry)

    session.action_count += 1

    read_results = kosmos_client.read_from_kosmos(doc_ref, target_ks_id, start, end, token)
    
    log_entry.result_summary = {"lines_read": len(read_results.get("lines", []))}

    db.commit()
    return read_results

def perform_agent_grep(db: Session, session_id: UUID, request: schemas.MultiGrepActionRequest, token: Optional[str]) -> Any:
    """Logs and executes a multi-document grep query via the Kosmos client."""
    session = _get_session_and_validate_for_action(db, session_id)
    
    payload = request.dict()

    # If no scope is provided, default to the session's target knowledge space
    scope = payload.get("scope", {})
    if not scope.get("document_ids") and not scope.get("knowledge_space_id"):
        target_ks_id = _get_target_ks_id(session)
        # Use str() to ensure UUID is ready for the final JSON payload to the backend
        scope["knowledge_space_id"] = str(target_ks_id)
    
    # Log all parameters for audit purposes, ensuring UUIDs are serialized correctly
    log_params = json.loads(json.dumps(payload, cls=CustomJsonEncoder))
    log_entry = models.ActionLog(session_id=session_id, action_type="grep", parameters=log_params)
    db.add(log_entry)
    
    session.action_count += 1
    
    # 调试信息
    print(f"[DEBUG] perform_agent_grep - session_id: {session_id}, token: {token[:20] if token else None}...")
    print(f"[DEBUG] perform_agent_grep - payload: {payload}")
    
    # The request schema now matches the backend, so we can pass it in directly
    grep_results = kosmos_client.multi_document_grep_in_kosmos(
        token=token,
        payload=payload
    )
    
    log_entry.result_summary = {"matches": grep_results.get("summary", {}).get("total_matches", 0)}
    
    db.commit()
    return grep_results

def add_evidence(db: Session, session_id: UUID, finding_id: UUID, evidence: schemas.EvidenceCreate) -> models.Evidence:
    """Adds an evidence record to a specific finding."""
    session = _get_session_and_validate_for_action(db, session_id)

    finding = next((f for f in session.findings if f.id == finding_id), None)
    if not finding:
        raise ValueError(f"Finding {finding_id} is not part of session {session_id}.")

    db_evidence = models.Evidence(**evidence.dict(), finding_id=finding_id)
    db.add(db_evidence)
    
    log_entry = models.ActionLog(session_id=session_id, action_type="add_evidence", parameters=json.dumps(evidence.dict()))
    db.add(log_entry)
    
    session.action_count += 1
    db.commit()
    db.refresh(db_evidence)
    
    # Automatically merge evidence for the session after adding new evidence
    from .session_service import merge_evidence_for_session
    merge_evidence_for_session(db, session_id)
    
    return db_evidence

def update_finding(db: Session, session_id: UUID, finding_id: UUID, finding_update: schemas.AssessmentFindingUpdate) -> models.AssessmentFinding:
    """Updates the judgement and comments for a specific finding."""
    session = _get_session_and_validate_for_action(db, session_id)

    finding = next((f for f in session.findings if f.id == finding_id), None)
    if not finding:
        raise ValueError(f"Finding {finding_id} is not part of session {session_id}.")
    
    # If the judgement is anything other than "Unable to Confirm", evidence is required.
    if finding_update.judgement != schemas.JudgementEnum.UNCONFIRMED and not finding.evidences:
        raise ValueError("Cannot add a finding with this judgement without at least one piece of evidence.")

    update_data = finding_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(finding, key, value)
    
    log_entry = models.ActionLog(session_id=session_id, action_type="update_finding", parameters=json.dumps(update_data))
    db.add(log_entry)

    session.action_count += 1
    db.commit()
    db.refresh(finding)
    return finding
