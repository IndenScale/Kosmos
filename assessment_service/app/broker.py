"""
Dramatiq broker setup for the Assessment Service.

This file is the single entrypoint for the Dramatiq workers for this service.
To run workers, use the command:
`dramatiq assessment_service.app.broker`
"""
import os
import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import Retries, AgeLimit, TimeLimit
from dotenv import load_dotenv
from periodiq import PeriodiqMiddleware

# Load environment variables from the project root .env file
# This ensures that the worker process has the same environment as the main app.
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

# Get Redis URL from environment, with a default for local development
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# --- Broker Initialization ---
# We use a RedisBroker, which is standard for Dramatiq.
# Add a robust stack of middleware.
redis_broker = RedisBroker(
    url=REDIS_URL,
    middleware=[
        PeriodiqMiddleware(skip_delay=60),
        AgeLimit(),
        TimeLimit(),
        Retries(min_backoff=1000, max_backoff=300000, max_retries=5),
    ]
)

# --- Set Global Broker ---
# Set this broker as the global instance for Dramatiq.
# This MUST be done before importing any modules that define actors.
dramatiq.set_broker(redis_broker)

# --- Actor Discovery ---
# This is the most important step for discovering our tasks.
# By importing the 'tasks' package, we trigger the execution of its __init__.py,
# which in turn imports the actors from their respective files, registering them.
from . import tasks