"""
Dramatiq actors for executing agent runs.
"""
import dramatiq
from ..database import SessionLocal
from ..services import agent_runner_service

@dramatiq.actor(
    queue_name="agent_runners", 
    max_retries=0, 
    time_limit=3600 * 2 * 1000  # 2-hour time limit in ms
)
def run_agent_task(session_id: str, queue_item_id: str, execution_config: dict):
    """
    Dramatiq actor to execute and monitor a single agent session.
    This runs in a dedicated queue for long-running tasks.
    """
    db = SessionLocal()
    try:
        # 1. Call the Executor to run the agent process synchronously
        completed_process_result = agent_runner_service.execute_agent_process(
            db=db,
            session_id=session_id,
            execution_config=execution_config
        )
        
        # 2. Call the Monitor to handle the result and update the DB
        agent_runner_service.monitor_agent_completion(
            db=db,
            session_id=session_id,
            result=completed_process_result,
            queue_item_id=queue_item_id
        )
    finally:
        db.close()
