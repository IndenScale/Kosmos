import uuid
from typing import Union
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..dependencies import get_reading_service, get_current_user
from ..services.reading_service import ReadingService
from ..services.bookmark_service import BookmarkService
from ..dependencies import get_reading_service, get_current_user, get_bookmark_service
from ..schemas.reading import DocumentReadResponse as ContentRead
from fastapi.responses import StreamingResponse
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from ..core.db import get_db
from ..models.membership import KnowledgeSpaceMember
from ..models.document import Document

router = APIRouter()

@router.get(
    "/{doc_ref}",
    response_model=ContentRead,
    summary="Read a portion of a document's content",
    description="Reads a specific portion of a document's canonical content, either by document ID or by a '@bookmark' name."
)
def read_document_content(
    doc_ref: str,
    knowledge_space_id: uuid.UUID = Query(None, description="Required when reading a bookmark. Specifies the knowledge space the bookmark belongs to."),
    start: Union[int, float] = Query(1, description="Start line number or percentage (e.g., 100 or 0.5). Ignored when using a bookmark."),
    end: Union[int, float, None] = Query(None, description="End line number or percentage. Ignored when using a bookmark."),
    max_lines: int = Query(200, description="Maximum number of lines to return."),
    max_chars: int = Query(8000, description="Maximum number of characters to return."),
    preserve_integrity: bool = Query(True, description="Avoid cutting lines in the middle to respect character limits."),
    reading_service: ReadingService = Depends(get_reading_service),
    bookmark_service: BookmarkService = Depends(get_bookmark_service),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves a chunk of a document's content with detailed metadata.
    The `doc_ref` can be a direct document UUID or a bookmark name prefixed with '@'.
    """
    doc_id_to_read = None
    start_to_read = start
    end_to_read = end

    if doc_ref.startswith('@'):
        bookmark_name = doc_ref[1:]
        if not knowledge_space_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Query parameter 'knowledge_space_id' is required when reading a bookmark.")

        bookmark = bookmark_service.resolve_bookmark_by_name(name=bookmark_name, ks_id=knowledge_space_id, user_id=current_user.id)
        
        if not bookmark.document_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Bookmark '@{bookmark_name}' is a container and not linked to a specific document.")
        
        doc_id_to_read = bookmark.document_id
        # When using a bookmark, its defined range overrides any query parameters
        start_to_read = bookmark.start_line if bookmark.start_line is not None else start
        end_to_read = bookmark.end_line if bookmark.end_line is not None else end
    else:
        try:
            doc_id_to_read = uuid.UUID(doc_ref)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid document ID or bookmark format. Bookmarks must start with '@'.")

    # --- Permission Check ---
    membership = db.query(KnowledgeSpaceMember).join(
        Document, Document.knowledge_space_id == KnowledgeSpaceMember.knowledge_space_id
    ).filter(
        Document.id == doc_id_to_read,
        KnowledgeSpaceMember.user_id == current_user.id
    ).first()
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this document.")

    return reading_service.read_document_content(
        document_id=doc_id_to_read,
        start=start_to_read,
        end=end_to_read,
        max_lines=max_lines,
        max_chars=max_chars,
        preserve_integrity=preserve_integrity
    )

@router.get(
    "/{document_id}/pages/{page_number}",
    summary="Get a single document page as an image",
    description="Renders a specific page of a document's PDF representation into a PNG image.",
    responses={
        200: {"content": {"image/png": {}}},
        404: {"description": "Document or page not found"},
        400: {"description": "Invalid page number"}
    }
)
def get_document_page_image(
    document_id: uuid.UUID,
    page_number: int,
    reading_service: ReadingService = Depends(get_reading_service),
    current_user: models.User = Depends(get_current_user)
):
    """
    Retrieves a specific page of a document, rendered as a PNG image.
    """
    image_stream = reading_service.get_pdf_page_image(
        document_id=document_id,
        page_number=page_number
    )
    return StreamingResponse(image_stream, media_type="image/png")

@router.post(
    "/{document_id}/pages/images",
    summary="Get multiple document pages as a ZIP archive",
    description="Renders specified pages or page ranges of a document's PDF representation into a single ZIP file containing PNG images.",
    responses={
        200: {"content": {"application/zip": {}}},
        404: {"description": "Document not found"},
        400: {"description": "Invalid page specification in request"}
    }
)
def get_document_pages_as_zip(
    document_id: uuid.UUID,
    request: schemas.reading.PageImageRequest,
    reading_service: ReadingService = Depends(get_reading_service),
    current_user: models.User = Depends(get_current_user)
):
    """
    Retrieves multiple pages of a document, rendered as PNG images and
    packaged in a ZIP file.
    """
    zip_stream = reading_service.get_pdf_pages_as_zip(
        document_id=document_id,
        pages_specs=request.pages
    )
    
    headers = {
        'Content-Disposition': f'attachment; filename="document_{document_id}_pages.zip"'
    }
    
    return StreamingResponse(zip_stream, media_type="application/zip", headers=headers)
