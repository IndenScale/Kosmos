import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, root_validator
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..dependencies import get_current_user, get_grep_service
from ..models import User
from ..services.grep.grep_service import GrepService
from ..schemas.grep import (
    MultiGrepRequest, MultiGrepResponse, GrepSummary
)

# --- Schemas (re-exporting from a central place) ---
__all__ = ["MultiGrepRequest", "MultiGrepResponse"]


# --- Router ---

router = APIRouter(
    tags=["Grep"],
)

@router.post(
    "/",
    response_model=MultiGrepResponse,
    summary="Perform regex search across multiple documents or a knowledge space"
)
def multi_document_grep(
    request: MultiGrepRequest,
    current_user: User = Depends(get_current_user),
    grep_service: GrepService = Depends(get_grep_service),
):
    """
    Performs a regular expression search across a specified scope:
    - A list of documents (`doc_ids`)
    - All documents within a knowledge space (`ks_id`)
    """
    doc_ids_to_search = grep_service.get_search_scope_and_verify_access(
        knowledge_space_id=request.scope.knowledge_space_id,
        document_ids=request.scope.document_ids,
        doc_ext=request.scope.doc_ext,
        current_user=current_user
    )

    results, total_matches, any_truncated = grep_service.perform_grep(
        doc_ids_to_search=doc_ids_to_search,
        request=request,
    )

    summary = GrepSummary(
        documents_searched=len(doc_ids_to_search),
        documents_with_matches=len(results),
        total_matches=total_matches,
        results_truncated=any_truncated
    )

    return MultiGrepResponse(summary=summary, results=results)
