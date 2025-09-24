import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Query

from ..core.db import get_db
from sqlalchemy.orm import Session
from ..models.user import User
from ..models.membership import KnowledgeSpaceMember
from ..dependencies import get_current_user, get_member_or_404, require_role
from ..services import knowledge_space_service, document_service
from ..schemas.knowledge_space import KnowledgeSpaceCreate, KnowledgeSpaceRead, KnowledgeSpaceUpdate, KnowledgeSpaceListItem
from ..schemas.membership import MemberAdd, MemberRead
from ..schemas.pagination import PaginatedResponse, PaginatedDocumentResponse
from ..schemas.document import DocumentBulkDeleteRequest, DocumentRead

router = APIRouter()

@router.post("/", response_model=KnowledgeSpaceRead, status_code=status.HTTP_201_CREATED)
def create_knowledge_space(
    ks_in: KnowledgeSpaceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new knowledge space. The creator becomes the owner."""
    return knowledge_space_service.create_knowledge_space(db=db, ks_in=ks_in, owner=current_user)

@router.get("/", response_model=PaginatedResponse[KnowledgeSpaceListItem])
def get_user_knowledge_spaces(
    cursor: str | None = Query(None),
    page_size: int = Query(20, gt=0, le=100),
    knowledge_space_id: uuid.UUID | None = Query(None, description="Filter by knowledge space ID"),
    name: str | None = Query(None, description="Filter by knowledge space name (partial match)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all knowledge spaces the current user is a member of, with cursor pagination and optional filters."""
    result = knowledge_space_service.get_user_knowledge_spaces_paginated(
        db=db, user=current_user, cursor=cursor, page_size=page_size,
        knowledge_space_id=knowledge_space_id, name=name
    )
    return PaginatedResponse(
        items=result["items"],
        total_count=result["total_count"],
        next_cursor=result["next_cursor"]
    )

from ..models.document import DocumentStatus

from ..utils import pagination_utils

@router.get("/{knowledge_space_id}/documents", response_model=PaginatedResponse[DocumentRead])
def get_documents_in_knowledge_space(
    knowledge_space_id: uuid.UUID,
    status: DocumentStatus | None = Query(None, description="Filter by document status."),
    filename: str | None = Query(None, description="Filter by filename (case-insensitive, partial match)."),
    extension: str | None = Query(None, description="Filter by file extension (e.g., 'pdf', 'docx')."),
    cursor: str | None = Query(None),
    page_size: int = Query(20, gt=0, le=100),
    db: Session = Depends(get_db),
    membership: KnowledgeSpaceMember = Depends(get_member_or_404), # Any member can view documents
):
    """
    Get documents within a specific knowledge space, with advanced filtering and pagination.
    """
    documents, total_count = document_service.get_documents_in_knowledge_space_paginated(
        db=db,
        knowledge_space_id=knowledge_space_id,
        cursor=cursor,
        page_size=page_size,
        status=status.value if status else None,
        original_filename_like=filename,
        extension=extension
    )
    
    # Build the rich response with summaries
    document_read_items = document_service.build_document_read_list_from_documents(db, documents)
    
    next_cursor = pagination_utils.encode_cursor(documents[-1].created_at) if len(documents) == page_size else None

    return PaginatedResponse(
        items=document_read_items,
        total_count=total_count,
        next_cursor=next_cursor
    )

@router.patch("/{knowledge_space_id}", response_model=KnowledgeSpaceRead)
def update_knowledge_space(
    knowledge_space_id: uuid.UUID,
    ks_in: KnowledgeSpaceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    membership: KnowledgeSpaceMember = Depends(require_role(["owner", "editor"])),
):
    """Update a knowledge space's name or ontology. Requires owner or editor role."""
    # We pass the current_user object to the service layer for authorship tracking
    return knowledge_space_service.update_knowledge_space(
        db=db, 
        db_ks=membership.knowledge_space, 
        ks_in=ks_in,
        current_user=current_user
    )

@router.delete("/{knowledge_space_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_knowledge_space(
    knowledge_space_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    membership: KnowledgeSpaceMember = Depends(require_role(["owner"])),
):
    """Delete a knowledge space. Only the owner can delete a knowledge space."""
    knowledge_space_service.delete_knowledge_space(
        db=db, 
        knowledge_space_id=knowledge_space_id,
        current_user=current_user
    )
    return None

@router.post("/{knowledge_space_id}/members", response_model=MemberRead)
def add_knowledge_space_member(
    knowledge_space_id: uuid.UUID,
    member_in: MemberAdd,
    db: Session = Depends(get_db),
    current_membership: KnowledgeSpaceMember = Depends(require_role(["owner", "editor"])),
):
    """Add a new member to a knowledge space. Requires owner or editor role."""
    new_member = knowledge_space_service.add_member(db=db, db_ks=current_membership.knowledge_space, member_in=member_in)
    if not new_member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User to be added not found")
    return new_member

@router.get("/{knowledge_space_id}/members", response_model=PaginatedResponse[MemberRead])
def get_knowledge_space_members(
    knowledge_space_id: uuid.UUID,
    cursor: str | None = Query(None),
    page_size: int = Query(50, gt=0, le=100),
    db: Session = Depends(get_db),
    membership: KnowledgeSpaceMember = Depends(get_member_or_404), # Any member can view the list
):
    """Get all members of a knowledge space, with cursor pagination. Requires being a member."""
    return knowledge_space_service.get_knowledge_space_members_paginated(
        db=db, knowledge_space_id=knowledge_space_id, cursor=cursor, page_size=page_size
    )

@router.delete("/{knowledge_space_id}/documents", status_code=status.HTTP_200_OK)
def delete_documents_in_knowledge_space(
    knowledge_space_id: uuid.UUID,
    payload: DocumentBulkDeleteRequest,
    db: Session = Depends(get_db),
    membership: KnowledgeSpaceMember = Depends(require_role(["owner", "editor"])),
):
    """
    Deletes a list of documents from the knowledge space.
    Requires owner or editor role.
    """
    deleted_count = document_service.delete_documents_by_ids(
        db=db,
        knowledge_space_id=knowledge_space_id,
        document_ids=payload.document_ids
    )
    return {"detail": f"Successfully deleted {deleted_count} document(s)."}
