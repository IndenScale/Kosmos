"""
Service layer for chunk-related business logic.
"""
import uuid
import base64
from typing import List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import asc
from .. import models
from .. import schemas

def get_chunk_by_id(db: Session, chunk_id: uuid.UUID) -> models.Chunk | None:
    """Gets a single chunk by its ID, eagerly loading its ontology tags."""
    return db.query(models.Chunk).options(
        joinedload(models.Chunk.ontology_tags)
    ).filter(models.Chunk.id == chunk_id).first()

def get_chunks_by_document_paginated(
    db: Session, 
    document_id: uuid.UUID, 
    cursor: str | None, 
    page_size: int
) -> dict:
    """
    Gets a paginated list of chunks for a specific document, ordered by their
    position in the document (start_line), eagerly loading ontology tags.
    """
    query = db.query(models.Chunk).options(
        joinedload(models.Chunk.ontology_tags)
    ).filter(models.Chunk.document_id == document_id)

    if cursor:
        try:
            # The cursor is the start_line of the last item from the previous page
            cursor_line = int(base64.urlsafe_b64decode(cursor).decode())
            query = query.filter(models.Chunk.start_line > cursor_line)
        except (ValueError, TypeError):
            pass # Ignore invalid cursors

    chunks = query.order_by(asc(models.Chunk.start_line)).limit(page_size + 1).all()

    next_cursor = None
    if len(chunks) > page_size:
        next_item = chunks[page_size]
        # The next cursor is the start_line of the next item
        next_cursor = base64.urlsafe_b64encode(str(next_item.start_line).encode()).decode()
        chunks = chunks[:page_size]

    return {"items": chunks, "next_cursor": next_cursor}
