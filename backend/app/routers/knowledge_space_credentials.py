"""
API endpoints for managing the link between Knowledge Spaces and Model Credentials.
"""
import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from .. import models
from ..schemas import credential_link as credential_link_schema
from ..schemas import credential as credential_schema
from ..core.db import get_db
from ..dependencies import get_current_user, require_role
from ..services.credential_link_service import CredentialLinkService

# This router will be included with a prefix, so we define routes relative to that.
# The tag provides a separate section in the API docs as requested.
router = APIRouter(
    tags=["Knowledge Space - Credentials"],
    # Permissions check: Only owners and editors can manage credential links.
    dependencies=[Depends(require_role(["owner", "editor"]))],
)

def get_credential_link_service(db: Session = Depends(get_db)) -> CredentialLinkService:
    return CredentialLinkService(db)

# --- Helper Function to build the response model ---

def _mask_api_key(encrypted_key: str | None) -> str:
    """Helper to create a masked version of an API key for display."""
    if not encrypted_key:
        return "Not Set"
    return f"enc_...{encrypted_key[-8:]}"

def _build_link_read_response(link: models.KnowledgeSpaceModelCredentialLink) -> credential_link_schema.CredentialLinkRead:
    """
    Manually constructs the Pydantic response model from the SQLAlchemy object,
    correctly handling the computed 'masked_api_key' field.
    """
    # 1. Create the nested credential read model with the computed field
    cred_read = credential_schema.ModelCredentialRead(
        **link.credential.__dict__,
        masked_api_key=_mask_api_key(link.credential.encrypted_api_key)
    )
    
    # 2. Create the main link read model using the nested Pydantic model
    return credential_link_schema.CredentialLinkRead(
        knowledge_space_id=link.knowledge_space_id,
        priority_level=link.priority_level,
        weight=link.weight,
        credential=cred_read
    )

# --- API Endpoints ---

@router.post(
    "/{knowledge_space_id}/credentials",
    response_model=credential_link_schema.CredentialLinkRead,
    status_code=status.HTTP_201_CREATED,
    summary="Link a Credential to a Knowledge Space"
)
def link_credential_to_knowledge_space(
    knowledge_space_id: uuid.UUID,
    link_in: credential_link_schema.CredentialLinkCreate,
    current_user: models.User = Depends(get_current_user),
    link_service: CredentialLinkService = Depends(get_credential_link_service),
):
    """
    Associate an existing model credential with a knowledge space, setting its
    priority and weight for use in AI tasks within that space.
    """
    new_link = link_service.link_credential(knowledge_space_id, link_in, current_user)
    return _build_link_read_response(new_link)

@router.get(
    "/{knowledge_space_id}/credentials",
    response_model=List[credential_link_schema.CredentialLinkRead],
    summary="List Linked Credentials for a Knowledge Space"
)
def list_linked_credentials(
    knowledge_space_id: uuid.UUID,
    link_service: CredentialLinkService = Depends(get_credential_link_service),
):
    """
    Retrieve all model credentials that are linked to a specific knowledge space,
    along with their priority and weight.
    """
    links = link_service.get_linked_credentials(knowledge_space_id)
    return [_build_link_read_response(link) for link in links]

@router.put(
    "/{knowledge_space_id}/credentials/{credential_id}",
    response_model=credential_link_schema.CredentialLinkRead,
    summary="Update a Credential Link"
)
def update_credential_link(
    knowledge_space_id: uuid.UUID,
    credential_id: uuid.UUID,
    update_data: credential_link_schema.CredentialLinkUpdate,
    link_service: CredentialLinkService = Depends(get_credential_link_service),
):
    """
    Update the priority and/or weight of an existing credential link.
    """
    updated_link = link_service.update_credential_link(knowledge_space_id, credential_id, update_data)
    return _build_link_read_response(updated_link)

@router.delete(
    "/{knowledge_space_id}/credentials/{credential_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unlink a Credential from a Knowledge Space"
)
def unlink_credential_from_knowledge_space(
    knowledge_space_id: uuid.UUID,
    credential_id: uuid.UUID,
    link_service: CredentialLinkService = Depends(get_credential_link_service),
):
    """
    Remove the association between a model credential and a knowledge space.
    """
    link_service.unlink_credential(knowledge_space_id, credential_id)
    return None
