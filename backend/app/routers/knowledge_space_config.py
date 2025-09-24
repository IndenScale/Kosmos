import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Any

from .. import models
from ..dependencies import get_db, get_current_user, require_role
from ..schemas.knowledge_space import AIConfigurationRead, AIConfigurationUpdate
from ..services import knowledge_space_service

router = APIRouter(
    prefix="/api/v1/knowledge-spaces",
    tags=["Knowledge Space Configuration"],
)

@router.get(
    "/{knowledge_space_id}/ai-configuration",
    response_model=AIConfigurationRead,
    summary="Get AI Configuration",
    description="Retrieves the complete AI model configuration for a specific knowledge space."
)
def read_ai_configuration(
    knowledge_space_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    # This dependency ensures the user is at least a member to view the config
    membership: models.KnowledgeSpaceMember = Depends(require_role(["owner", "admin", "editor", "viewer"])),
) -> Any:
    """
    Fetches the AI configuration for a knowledge space.
    The user must be a member of the knowledge space.
    """
    db_ks = knowledge_space_service.get_knowledge_space_by_id(db, knowledge_space_id)
    if not db_ks:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge space not found")
    
    return knowledge_space_service.get_ai_configuration(db_ks)

@router.put(
    "/{knowledge_space_id}/ai-configuration",
    response_model=AIConfigurationRead,
    summary="Update AI Configuration",
    description="Partially updates the AI model configuration for a knowledge space. Only the provided fields will be updated."
)
def update_ai_configuration(
    knowledge_space_id: uuid.UUID,
    config_in: AIConfigurationUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    # This dependency ensures the user has rights to edit the knowledge space
    membership: models.KnowledgeSpaceMember = Depends(require_role(["owner", "admin"])),
) -> Any:
    """
    Updates the AI configuration for a knowledge space.
    The user must have 'owner' or 'admin' rights for the knowledge space.
    """
    db_ks = knowledge_space_service.get_knowledge_space_by_id(db, knowledge_space_id)
    if not db_ks:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge space not found")

    return knowledge_space_service.update_ai_configuration(db, db_ks, config_in)
