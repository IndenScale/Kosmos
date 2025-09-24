"""
Dramatiq actors for scheduling tasks.
"""
import dramatiq
import logging
import os
from logging.handlers import RotatingFileHandler
from periodiq import cron

from ..database import SessionLocal
from ..services import execution_service

LOG_DIR = "logs/assessment_service"
LOG_FILE = os.path.join(LOG_DIR, "monitor.log")

def setup_monitor_logger():
    """Sets up a rotating file logger for the scheduler monitor."""
    os.makedirs(LOG_DIR, exist_ok=True)
    logger = logging.getLogger("scheduler_monitor")
    logger.setLevel(logging.INFO)

    # Avoid adding duplicate handlers if the actor is reloaded
    if not logger.handlers:
        # Use RotatingFileHandler for log size management
        handler = RotatingFileHandler(
            LOG_FILE, 
            maxBytes=10*1024*1024,  # 10 MB
            backupCount=5  # Keep 5 backup logs
        )
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger

# Initialize the logger once when the module is loaded
monitor_logger = setup_monitor_logger()


# This actor acts as a daemon, periodically checking for work to do.
@dramatiq.actor(
    queue_name="default", # This should be a quick task running in the default queue
    periodic=cron('* * * * *') # Run every minute
)
def scheduler_tick():
    """
    Periodically calls the session scheduler and logs the outcome.
    """
    monitor_logger.info("Scheduler tick running...")
    db = SessionLocal()
    dispatched_session_id = None
    try:
        dispatched_session_id = execution_service.schedule_next_session(db)
        if dispatched_session_id:
            monitor_logger.info(f"Successfully dispatched session: {dispatched_session_id}")
        else:
            monitor_logger.info("No pending sessions to schedule at this time.")
    except Exception as e:
        monitor_logger.error(f"An error occurred during scheduler tick: {e}", exc_info=True)
    finally:
        db.close()