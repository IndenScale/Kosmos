"""
Service for enqueuing and scheduling assessment jobs.
This service handles the creation of sessions and dispatching them to a
Dramatiq queue for asynchronous execution.
"""
import logging
import math
import os
from dotenv import load_dotenv
from sqlalchemy.orm import Session, selectinload

from .. import models, schemas
from .session_service import create_session, start_assessment

# Load system-wide default models from the .env file
MODELS_ENV_PATH = '/home/hxdi/Kosmos/models.env'
if os.path.exists(MODELS_ENV_PATH):
    load_dotenv(dotenv_path=MODELS_ENV_PATH)

class AgentDispatchError(Exception):
    """Exception raised when agent dispatch fails."""
    pass

def enqueue_job_sessions(db: Session, job_id: str, request: schemas.JobExecutionRequest) -> schemas.JobExecutionResponse:
    """
    Calculates, creates, and queues all required sessions for a given job.
    This function is called by the API and returns immediately after enqueuing.
    """
    logging.info(f"Starting to enqueue sessions for job_id={job_id}")
    job = db.query(models.AssessmentJob).options(selectinload(models.AssessmentJob.findings)).filter(models.AssessmentJob.id == job_id).first()
    if not job:
        raise ValueError(f"Job with id {job_id} not found.")

    existing_queue_items = db.query(models.ExecutionQueue).filter(models.ExecutionQueue.job_id == job_id).count()
    if existing_queue_items > 0:
        raise PermissionError(f"Job {job_id} is already enqueued or running.")

    pending_findings = db.query(models.AssessmentFinding).filter(
        models.AssessmentFinding.job_id == job_id,
        models.AssessmentFinding.session_id.is_(None)
    ).all()

    logging.info(f"Job has {len(job.findings)} total findings, {len(pending_findings)} are pending assignment.")

    if not pending_findings:
        return schemas.JobExecutionResponse(
            status="no_action",
            job_id=job_id,
            total_sessions_created=0,
            message="Job has no pending findings to assess."
        )

    # --- Fallback Logic for Agent Model Configuration ---
    base_url = request.openai_base_url or os.getenv("AGENT_BASE_URL")
    api_key = request.openai_api_key or os.getenv("AGENT_API_KEY")
    model_name = request.openai_model or os.getenv("AGENT_MODEL_NAME")

    if not (base_url and model_name):
        raise AgentDispatchError("Model configuration is missing. No model provided in the request and no AGENT model configured in system environment.")
    # --- End of Fallback Logic ---

    batch_size = request.session_batch_size
    total_sessions_needed = math.ceil(len(pending_findings) / batch_size)
    logging.info(f"Calculated {total_sessions_needed} sessions needed for {len(pending_findings)} findings with batch size {batch_size}.")

    sessions_created_count = 0
    try:
        for i in range(0, len(pending_findings), batch_size):
            findings_chunk = pending_findings[i:i + batch_size]
            if not findings_chunk:
                continue

            new_session = create_session(db=db, job_id=job_id, findings_batch=findings_chunk)

            if new_session:
                logging.info(f"create_session returned new session with id={new_session.id}. Adding to queue.")
                execution_config = {
                    "agent": request.agent.value,
                    "session_batch_size": request.session_batch_size,
                    "openai_base_url": base_url,  # Use resolved value
                    "openai_api_key": api_key,    # Use resolved value
                    "openai_model": model_name,  # Use resolved value
                    "kosmos_username": request.kosmos_username,
                    "kosmos_password": request.kosmos_password,
                    "agent_prompt": request.agent_prompt
                }
                queue_entry = models.ExecutionQueue(
                    session_id=new_session.id,
                    job_id=job_id,
                    execution_config=execution_config
                )
                db.add(queue_entry)
                sessions_created_count += 1
        
        if sessions_created_count > 0:
            db.commit()
        else:
            db.rollback()

    except Exception as e:
        db.rollback()
        logging.error(f"An error occurred during session creation loop: {e}", exc_info=True)
        raise AgentDispatchError(f"Failed to create sessions and queue entries: {e}")

    if sessions_created_count > 0:
        logging.info(f"Session enqueuing complete for job {job_id}. A periodic scheduler will dispatch the agents.")

    return schemas.JobExecutionResponse(
        status="queued",
        job_id=str(job_id),
        total_sessions_created=sessions_created_count,
        message=f"Successfully created and queued {sessions_created_count} sessions for job {job_id}."
    )

def schedule_next_session(db: Session) -> str | None:
    """
    Checks for running sessions and dispatches the next pending session via Dramatiq.
    This function is intended to be called by a periodic task (daemon).

    Returns:
        The ID of the dispatched session, or None if no session was dispatched.
    """
    session_id_to_dispatch = None
    queue_item_id_to_dispatch = None
    config_to_dispatch = None

    try:
        with db.begin_nested():
            processing_count = db.query(models.ExecutionQueue).filter(models.ExecutionQueue.status == 'PROCESSING').count()
            if processing_count > 0:
                return None

            next_item = db.query(models.ExecutionQueue).filter(models.ExecutionQueue.status == 'PENDING').order_by(models.ExecutionQueue.created_at).first()
            if not next_item:
                return None

            logging.info(f"Scheduler: Found next session to process: {next_item.session_id}")

            next_item.status = 'PROCESSING'
            start_assessment(db=db, session_id=next_item.session_id)
            
            session_id_to_dispatch = str(next_item.session_id)
            queue_item_id_to_dispatch = str(next_item.id)
            config_to_dispatch = next_item.execution_config

        db.commit()
        logging.info(f"Scheduler: Marked session {session_id_to_dispatch} as PROCESSING.")

    except Exception as e:
        db.rollback()
        logging.error(f"Scheduler failed to lock next session: {e}", exc_info=True)
        return None

    if session_id_to_dispatch:
        try:
            from ..tasks.agent_tasks import run_agent_task
            run_agent_task.send(
                session_id=session_id_to_dispatch,
                queue_item_id=queue_item_id_to_dispatch,
                execution_config=config_to_dispatch
            )
            logging.info(f"Scheduler: Dispatched task for session {session_id_to_dispatch} to Dramatiq.")
            return session_id_to_dispatch
        except Exception as e:
            logging.error(f"FATAL: Scheduler failed to send task to Dramatiq for session {session_id_to_dispatch}: {e}", exc_info=True)
            try:
                db.rollback()
                queue_item = db.query(models.ExecutionQueue).filter(models.ExecutionQueue.id == queue_item_id_to_dispatch).first()
                if queue_item:
                    queue_item.status = 'PENDING'
                    session = db.query(models.AssessmentSession).filter(models.AssessmentSession.id == session_id_to_dispatch).first()
                    if session and session.status == schemas.SessionStatus.ASSESSING_CONTROLS:
                        session.status = schemas.SessionStatus.READY_FOR_ASSESSMENT
                    db.commit()
                    logging.info(f"Successfully rolled back queue and session status for session {session_id_to_dispatch} to PENDING/READY.")
            except Exception as rollback_e:
                logging.error(f"FATAL: Failed to rollback state for session {session_id_to_dispatch}: {rollback_e}", exc_info=True)
    
    return None
