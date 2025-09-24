import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, UploadFile, File, Query, HTTPException, status
from pydantic import BaseModel, Field, model_validator

from ..services.ingestion.service import IngestionService
from ..models.user import User
from ..models.document import Document
from ..models.domain_events.ingestion_events import ContentExtractionStrategy, AssetAnalysisStrategy
from ..schemas.document import DocumentRead
from ..dependencies import get_ingestion_service, get_current_user

router = APIRouter()

class ReingestionRequest(BaseModel):
    """Request body for re-ingesting documents."""
    document_ids: Optional[List[uuid.UUID]] = Field(default=None, description="A list of document IDs to re-ingest.")
    knowledge_space_id: Optional[uuid.UUID] = Field(default=None, description="The ID of a knowledge space to re-ingest all its documents.")
    
    force: bool = Field(True, description="If true, forces reprocessing even if content has been processed before.")
    
    content_extraction_strategy: Optional[ContentExtractionStrategy] = Field(None, description="Strategy for content extraction.")
    asset_analysis_strategy: Optional[AssetAnalysisStrategy] = Field(None, description="Strategy for asset analysis.")
    chunking_strategy_name: Optional[str] = Field(None, description="Name of the chunking strategy to use.")

    @model_validator(mode='after')
    def check_exclusive_ids(self):
        if (not self.document_ids and not self.knowledge_space_id) or \
           (self.document_ids and self.knowledge_space_id):
            raise ValueError('Either document_ids or knowledge_space_id must be provided, but not both.')
        return self


@router.post(
    "/upload",
    response_model=DocumentRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload and Ingest a Document",
    description="""
    Uploads a new document, registers it and any potential children (from containers like ZIPs),
    and publishes domain events to trigger the full ingestion pipeline.
    This is the primary, event-driven endpoint for adding new content.
    """
)
async def upload_and_ingest_document(
    knowledge_space_id: uuid.UUID = Query(..., description="The ID of the knowledge space to upload the document to"),
    file: UploadFile = File(...),
    force: bool = Query(False, description="If true, forces reprocessing even if content has been processed before."),
    content_extraction_strategy: Optional[ContentExtractionStrategy] = Query(None, description="Strategy for content extraction."),
    asset_analysis_strategy: Optional[AssetAnalysisStrategy] = Query(None, description="Strategy for asset analysis."),
    chunking_strategy_name: Optional[str] = Query(None, description="Name of the chunking strategy to use."),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
    current_user: User = Depends(get_current_user),
):
    """
    Handles the upload and registration of a new document, kicking off the
    asynchronous, event-driven ingestion process.
    """
    try:
        # The ingestion service now handles the entire registration process,
        # including container extraction and event publication.
        parent_document = await ingestion_service.ingest_document(
            knowledge_space_id=knowledge_space_id,
            file=file,
            uploader=current_user,
            force=force,
            content_extraction_strategy=content_extraction_strategy,
            asset_analysis_strategy=asset_analysis_strategy,
            chunking_strategy_name=chunking_strategy_name,
        )
        # We can return the parent document's data immediately.
        # The actual processing happens in the background.
        return DocumentRead.model_validate(parent_document)
    except HTTPException:
        # Re-raise HTTP exceptions directly
        raise
    except Exception as e:
        # Catch-all for unexpected errors from the service layer
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during ingestion: {str(e)}"
        )

@router.post(
    "/re-ingest",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Re-ingest Existing Documents",
    description="""
    Triggers the re-ingestion process for a specified list of documents or all documents
    within a knowledge space. Allows for fine-grained control over processing strategies.
    """
)
async def re_ingest_documents(
    request: ReingestionRequest,
    ingestion_service: IngestionService = Depends(get_ingestion_service),
    current_user: User = Depends(get_current_user),
):
    """
    Handles the re-ingestion of existing documents by creating new domain events
    to trigger the processing pipeline again.
    """
    try:
        count = ingestion_service.reingest_documents(
            document_ids=request.document_ids,
            knowledge_space_id=request.knowledge_space_id,
            uploader=current_user,
            force=request.force,
            content_extraction_strategy=request.content_extraction_strategy,
            asset_analysis_strategy=request.asset_analysis_strategy,
            chunking_strategy_name=request.chunking_strategy_name,
        )
        return {"message": f"Successfully scheduled {count} documents for re-ingestion."}
    except HTTPException:
        # Re-raise HTTP exceptions directly
        raise
    except ValueError as e:
        # Handle cases like documents or KS not found
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        # Catch-all for unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during re-ingestion: {str(e)}"
        )
