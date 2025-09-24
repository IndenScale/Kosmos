# backend/app/tasks/service_factory.py
"""
Service Factory for Dramatiq Workers.

This module provides functions to instantiate services with their dependencies
(like DB sessions and Redis clients) for use within background tasks.
This avoids the circular dependency issues that arise from trying to use
the FastAPI dependency injection system in a worker context.
"""
from contextlib import contextmanager
from sqlalchemy.orm import Session

# Import core dependency creators
from ..core.db import SessionLocal
from ..core.redis_client import get_redis_client
from ..core.object_storage import get_minio_client

# Import all necessary services
from ..services import JobService
from ..services.reading_service import ReadingService
from ..services.ai_provider_service import AIProviderService
from ..services.ontology_service import OntologyService

@contextmanager
def get_services_scope():
    """
    Provides a transactional scope for services used in a task.
    Ensures that all services within a single task execution share the
    same database session and that the session is properly closed.
    """
    db = SessionLocal()
    redis_client = get_redis_client()
    minio_client = get_minio_client()
    try:
        # AIProviderService is stateless and only needs a db session, 
        # so we can create it here to be passed to other services.
        ai_provider_service = AIProviderService(db=db)
        
        yield {
            "db": db,
            "job_service": JobService(db=db, redis_client=redis_client, minio_client=minio_client),
            "reading_service": ReadingService(db=db, minio=minio_client),
            "ai_provider_service": ai_provider_service,
            "ontology_service": OntologyService(db=db),
            "minio_client": minio_client
        }
    finally:
        db.close()
