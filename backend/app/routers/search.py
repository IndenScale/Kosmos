"""
API endpoint for all search-related queries.
"""
import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..dependencies import get_current_user
from ..models.user import User
from ..services.search.schemas import SearchRequest, SearchResponse
from ..services.search.search_service import SearchService

router = APIRouter()

@router.post("/", response_model=SearchResponse)
def perform_search(
    request: SearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Main endpoint to perform a search query within a knowledge space.

    - **query**: The user's search query.
    - **knowledge_space_id**: The ID of the knowledge space to search in.
    - **top_k**: The number of results to return.
    - **filters**: Hard constraints to apply (e.g., document_id).
    - **boosters**: Soft constraints to influence ranking.
    """
    search_service = SearchService(db)
    response = search_service.search(request, current_user.id)
    return response
