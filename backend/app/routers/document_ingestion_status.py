"""
API router for checking document ingestion status in a knowledge space.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from ..core.db import get_db
from .. import services, schemas

router = APIRouter(
    tags=["Document Ingestion Status"]
)

@router.get("/{knowledge_space_id}/ingestion-status", response_model=schemas.DocumentIngestionStatusResponse)
def get_document_ingestion_status(
    knowledge_space_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Check the ingestion status of all documents in a knowledge space.
    
    This endpoint:
    1. Gets all valid documents (excluding unsupported file types)
    2. Checks for canonical content
    3. Calculates asset analysis completion rate
    4. Identifies pending jobs that might be blocking analysis
    
    Returns:
        DocumentIngestionStatusResponse: Status information for all documents
    """
    try:
        # Import the service function dynamically to avoid circular imports
        from ..services.document_ingestion_status_service import check_document_ingestion_status
        return check_document_ingestion_status(db=db, knowledge_space_id=knowledge_space_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking document ingestion status: {str(e)}")