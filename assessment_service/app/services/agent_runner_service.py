"""
Service functions for running and monitoring a single agent process.
This service encapsulates the logic for preparing, executing, and handling
the completion of an external agent subprocess.
"""
import subprocess
import os
import logging
from pathlib import Path
from sqlalchemy.orm import Session

from .. import models, schemas

class AgentExecutionError(Exception):
    """Custom exception for errors during agent execution."""
    pass

def execute_agent_process(db: Session, session_id: str, execution_config: dict) -> subprocess.CompletedProcess:
    """
    Prepares and executes a single agent process synchronously.

    This function is the "Executor". It builds the command, sets up the
    environment, and calls subprocess.run, blocking until the agent
    process completes.

    Args:
        db: The database session.
        session_id: The ID of the assessment session to execute.
        execution_config: A dictionary containing all execution parameters
                          (agent type, credentials, etc.).

    Returns:
        A subprocess.CompletedProcess object with the result of the execution.
    """
    session = db.query(models.AssessmentSession).filter(models.AssessmentSession.id == session_id).first()
    if not session:
        raise AgentExecutionError(f"Session with id {session_id} not found.")

    job = db.query(models.AssessmentJob).filter(models.AssessmentJob.id == session.job_id).first()
    if not job:
        raise AgentExecutionError(f"Job with id {session.job_id} not found.")

    target_ks = next((ks for ks in job.knowledge_spaces if ks.role == "target"), None)
    if not target_ks or not hasattr(target_ks, 'ks_id'):
        raise AgentExecutionError(f"Job {job.id} does not have a target knowledge space configured.")
    knowledge_space_id = target_ks.ks_id

    log_dir = Path("logs/agent_sessions")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file_path = log_dir / f"{session.id}.log"

    agent_command_map = {
        schemas.AgentType.QWEN: "qwen",
        schemas.AgentType.GEMINI_CLI: "gemini",
        schemas.AgentType.CLAUDE: "claude",
    }
    agent_executable = agent_command_map.get(execution_config.get('agent'), "qwen")

    guide_path = Path("docs/Agent_Assessment_SOP_Non_Interactive.md")
    try:
        with open(guide_path, "r", encoding="utf-8") as f:
            workflow_guide = f.read()
    except FileNotFoundError:
        workflow_guide = "Error: The Agent Workflow Guide was not found."

    # Use custom agent_prompt if provided, otherwise use the default
    if execution_config.get('agent_prompt'):
        prompt = execution_config['agent_prompt']
    else:
        prompt = f"""
# 评估任务简报
**核心指令：请务必使用中文进行思考、推理和决策。你所有的内心独白和输出都必须是中文，以便于审计。**
你是一个自动化评估代理。你的任务是根据在一个指定知识空间内找到的证据，来评估一组控制项。

## 关键信息
- **知识空间 ID**: {knowledge_space_id}
- **评估任务 ID**: {session.job_id}
- **当前会话 ID**: {session.id}

## 你的标准作业流程 (SOP)
你**必须**严格遵循以下步骤。
---
{workflow_guide}
---
现在开始评估。
"""

    command = [agent_executable, "-p", prompt, "--approval-mode=yolo"]
    process_env = os.environ.copy()
    process_env["KOSMOS_ASSESSMENT_SESSION_ID"] = str(session.id)
    process_env["KOSMOS_MODE"] = "AGENT"

    # Set Kosmos credentials
    if execution_config.get('kosmos_username'):
        process_env["KOSMOS_USERNAME"] = execution_config['kosmos_username']
    if execution_config.get('kosmos_password'):
        process_env["KOSMOS_PASSWORD"] = execution_config['kosmos_password']
        
    # Set OpenAI specific credentials if applicable
    if execution_config.get('agent') == schemas.AgentType.QWEN:
        if execution_config.get('openai_base_url'):
            process_env["OPENAI_BASE_URL"] = execution_config['openai_base_url']
        if execution_config.get('openai_api_key'):
            process_env["OPENAI_API_KEY"] = execution_config['openai_api_key']
        if execution_config.get('openai_model'):
            process_env["OPENAI_MODEL"] = execution_config['openai_model']

    # Update session with log file URL before execution
    session.log_file_url = str(log_file_path.resolve())
    db.commit()

    logging.info(f"Starting synchronous agent execution for session {session.id}")
    logging.info(f"Command: {' '.join(command)}")
    logging.info(f"Log file: {log_file_path.resolve()}")

    try:
        with open(log_file_path, "w", encoding="utf-8") as log_file:
            result = subprocess.run(
                command,
                env=process_env,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                timeout=3600  # 1-hour timeout
            )
        logging.info(f"Agent process for session {session.id} finished with return code: {result.returncode}")
        return result
    except subprocess.TimeoutExpired as e:
        logging.error(f"Agent execution timeout for session {session.id}")
        # Create a mock result for timeout case
        return subprocess.CompletedProcess(command, returncode=-9, stdout=str(e), stderr="TimeoutExpired")
    except Exception as e:
        logging.error(f"Agent execution failed for session {session.id}: {e}", exc_info=True)
        # Create a mock result for other exceptions
        return subprocess.CompletedProcess(command, returncode=-1, stdout=str(e), stderr=str(e))


def monitor_agent_completion(db: Session, session_id: str, result: subprocess.CompletedProcess, queue_item_id: str):
    """
    Monitors and handles the completion of an agent process.

    This function is the "Monitor". It inspects the result of the agent
    process and updates the database state accordingly.

    Args:
        db: The database session.
        session_id: The ID of the session that was executed.
        result: The CompletedProcess object from the executor.
        queue_item_id: The ID of the execution queue item.
    """
    try:
        session = db.query(models.AssessmentSession).filter(models.AssessmentSession.id == session_id).first()
        queue_item = db.query(models.ExecutionQueue).filter(models.ExecutionQueue.id == queue_item_id).first()

        if not session or not queue_item:
            logging.error(f"Session {session_id} or queue item {queue_item_id} not found during completion handling.")
            return

        logging.info(f"Monitoring completion for session {session_id}, current status: {session.status}")

        # If agent process finished but session wasn't submitted by the agent, it's an issue.
        if session.status == schemas.SessionStatus.ASSESSING_CONTROLS:
            logging.warning(
                f"Agent process for session {session_id} ended but session status is still ASSESSING_CONTROLS. "
                f"Return code: {result.returncode}. Agent may have failed to call 'submit'."
            )
            session.warning_count += 1
            
            if result.returncode == 0:
                # Process exited cleanly but didn't submit. Mark for review.
                session.status = schemas.SessionStatus.SUBMITTED_FOR_REVIEW
                logging.info(f"Session {session_id} marked as SUBMITTED_FOR_REVIEW due to incomplete agent behavior.")
            else:
                # Process exited with an error. Mark as FAILED.
                session.status = schemas.SessionStatus.FAILED
                session.error_count += 1
                logging.error(f"Session {session_id} marked as FAILED due to agent process error (return code: {result.returncode})")
        
        # Mark the queue item as completed
        if queue_item.status == 'PROCESSING':
            queue_item.status = 'COMPLETED'
            logging.info(f"Queue item {queue_item_id} for session {session_id} marked as COMPLETED.")
        
        db.commit()

    except Exception as e:
        db.rollback()
        logging.error(f"Error during agent completion monitoring for session {session_id}: {e}", exc_info=True)
