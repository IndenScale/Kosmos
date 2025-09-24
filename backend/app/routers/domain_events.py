import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..models.domain_events import DomainEvent, EventStatus
from ..models.user import User
from ..dependencies import get_current_user, require_super_admin
from ..schemas.pagination import PaginatedResponse
from ..schemas.domain_event import DomainEventRead
from ..utils.pagination_utils import create_paginated_response, decode_cursor

router = APIRouter()

@router.get(
    "/",
    response_model=PaginatedResponse[DomainEventRead],
    summary="List and Filter Domain Events",
    dependencies=[Depends(require_super_admin)]
)
def list_domain_events(
    db: Session = Depends(get_db),
    event_type: Optional[str] = Query(None, description="Filter by event type (e.g., 'DocumentRegisteredPayload')."),
    status: Optional[EventStatus] = Query(None, description="Filter by event processing status."),
    aggregate_id: Optional[str] = Query(None, description="Filter by aggregate ID (e.g., a document ID)."),
    page_size: int = Query(20, ge=1, le=100, description="Number of events per page."),
    cursor: Optional[str] = Query(None, description="Cursor for pagination."),
):
    """
    Provides a way to query the domain events outbox.
    This is useful for system monitoring, debugging, and auditing.
    Requires super admin privileges.
    """
    query = db.query(DomainEvent)

    if event_type:
        query = query.filter(DomainEvent.event_type == event_type)
    if status:
        query = query.filter(DomainEvent.status == status)
    if aggregate_id:
        query = query.filter(DomainEvent.aggregate_id == aggregate_id)

    # Get total count before pagination
    total_count = query.count()

    # Apply cursor-based pagination
    if cursor:
        cursor_time = decode_cursor(cursor)
        if cursor_time:
            query = query.filter(DomainEvent.created_at < cursor_time)

    events = query.order_by(DomainEvent.created_at.desc()).limit(page_size).all()

    paginated_data = create_paginated_response(
        items=[DomainEventRead.model_validate(event) for event in events],
        page_size=page_size,
        get_cursor_func=lambda item: item.created_at
    )

    return {
        "items": paginated_data["items"],
        "total_count": total_count,
        "next_cursor": paginated_data["next_cursor"]
    }
