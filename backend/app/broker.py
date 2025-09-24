# backend/app/broker.py
"""
This is the single, explicit entrypoint for the Dramatiq worker.
It ensures that the message broker is configured correctly before any actors
are imported or the worker starts running.

To start the worker, run:
`dramatiq backend.app.broker`
"""
# --- Environment Loading ---
# This MUST be the first thing to run, to ensure all subsequent imports
# have access to the correct environment variables from the .env file.
from dotenv import load_dotenv
import os

# Load the .env file from the project root (one level up from the `backend` directory)
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
load_dotenv(dotenv_path=dotenv_path)
print(f"--- [Broker Setup] Loading environment variables from: {dotenv_path} ---")
# --- End of Environment Loading ---

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import Middleware
from .core.config import settings
from .database import SessionLocal

# 1. Define a middleware for SQLAlchemy session management.
class SQLAlchemyMiddleware(Middleware):
    """A Dramatiq middleware for managing SQLAlchemy database sessions."""
    def __init__(self, Session):
        self.Session = Session

    def before_process_message(self, broker, message):
        """Creates a new session before processing each message."""
        message.options['db_session'] = self.Session()

    def after_process_message(self, broker, message, *, result=None, exception=None):
        """Closes the session after processing each message."""
        session = message.options.get('db_session')
        if session:
            if exception:
                session.rollback()
            else:
                session.commit()
            session.close()

# 2. Create a RedisBroker instance and add the SQLAlchemy middleware.
print("--- [Broker Setup] Configuring Dramatiq RedisBroker ---")
print(f"--- [Broker Setup] Host: {settings.REDIS_HOST}, Port: {settings.REDIS_PORT}, DB: {settings.REDIS_DB} ---")
redis_broker = RedisBroker(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    middleware=[SQLAlchemyMiddleware(SessionLocal)],
    # 消息过期时间：1小时，废弃启动前的旧任务
    default_queue_name="default",
    dead_message_ttl=3600000  # 1小时 = 3600秒 * 1000毫秒
)

# 3. Set this broker as the global broker for Dramatiq.
dramatiq.set_broker(redis_broker)
print("--- [Broker Setup] Broker has been set globally with SQLAlchemy middleware. ---")


# 4. Import all actor modules here.
print("--- [Broker Setup] Importing actor modules... ---")
from .tasks import document_processing
from .tasks import chunking
from .tasks import asset_analyzing
print("--- [Broker Setup] All actor modules imported. Worker is ready. ---")
