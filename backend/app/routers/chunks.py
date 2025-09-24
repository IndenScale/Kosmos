"""
API endpoints for accessing document chunks.
"""
import uuid
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..dependencies import get_current_user, get_document_and_verify_membership, get_member_or_404
from ..models import User, Document, Chunk
from ..services import chunk_service
from ..schemas import chunk as chunk_schema

router = APIRouter()

@router.get(
    "/documents/{document_id}/chunks",
    response_model=chunk_schema.PaginatedChunkResponse,
    summary="List chunks for a document"
)
def list_document_chunks(
    document_id: uuid.UUID,
    cursor: str | None = Query(None, description="Cursor for pagination (based on start_line)"),
    page_size: int = Query(50, gt=0, le=200, description="Number of chunks per page"),
    db: Session = Depends(get_db),
    # This dependency ensures the user has access to the document
    document: Document = Depends(get_document_and_verify_membership),
):
    """
    Retrieve a paginated list of all chunks associated with a specific document.
    Requires membership to the knowledge space the document belongs to.
    """
    return chunk_service.get_chunks_by_document_paginated(
        db=db, document_id=document_id, cursor=cursor, page_size=page_size
    )

@router.get(
    "/{chunk_id}",
    response_model=chunk_schema.ChunkRead,
    summary="Get a specific chunk by ID"
)
def get_chunk_details(
    chunk_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve the details of a single chunk by its ID.
    Requires membership to the knowledge space the chunk's document belongs to.
    """
    chunk = chunk_service.get_chunk_by_id(db, chunk_id=chunk_id)
    
    if not chunk:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chunk not found")

    # Security check: Verify the user has access to the knowledge space
    # by checking their membership for the chunk's parent document.
    get_member_or_404(
        knowledge_space_id=chunk.document.knowledge_space_id,
        db=db,
        current_user=current_user
    )
    
    return chunk
