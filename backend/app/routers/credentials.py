import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models
from ..schemas import credential as credential_schema
from ..services.credential_service import CredentialService
from ..core.db import get_db
from ..dependencies import get_current_user

router = APIRouter(
    dependencies=[Depends(get_current_user)],
)

def _mask_api_key(encrypted_key: str | None) -> str:
    """Helper to create a masked version of an API key for display."""
    if not encrypted_key:
        return "Not Set"
    # A real implementation might show last 4 chars, but this is safer
    return f"enc_...{encrypted_key[-8:]}"

@router.post(
    "/",
    response_model=credential_schema.ModelCredentialRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new model credential"
)
def create_new_credential(
    cred_in: credential_schema.ModelCredentialCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Create a new AI model credential for the currently authenticated user.
    The API key will be securely encrypted before storage.
    """
    service = CredentialService(db)
    db_cred = service.create_credential(owner_id=current_user.id, cred_in=cred_in)

    return credential_schema.ModelCredentialRead(
        **db_cred.__dict__,
        masked_api_key=_mask_api_key(db_cred.encrypted_api_key)
    )

@router.get(
    "/",
    response_model=List[credential_schema.ModelCredentialRead],
    summary="List all of your model credentials"
)
def list_my_credentials(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Retrieve all AI model credentials owned by the currently authenticated user.
    """
    service = CredentialService(db)
    credentials = service.get_user_credentials(user_id=current_user.id)
    return [
        credential_schema.ModelCredentialRead(
            **cred.__dict__,
            masked_api_key=_mask_api_key(cred.encrypted_api_key)
        ) for cred in credentials
    ]

@router.get(
    "/{cred_id}",
    response_model=credential_schema.ModelCredentialRead,
    summary="Get a specific model credential"
)
def get_credential(
    cred_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Get details of a specific AI model credential.
    You must be the owner of the credential to view it.
    """
    service = CredentialService(db)
    credential = service.get_credential_by_id(cred_id)
    
    # Check if the current user owns this credential
    if credential.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found"
        )
    
    return credential_schema.ModelCredentialRead(
        **credential.__dict__,
        masked_api_key=_mask_api_key(credential.encrypted_api_key)
    )

@router.delete(
    "/{cred_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a model credential"
)
def delete_a_credential(
    cred_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Delete a specific AI model credential.
    You must be the owner of the credential to delete it.
    """
    service = CredentialService(db)
    service.delete_credential(user_id=current_user.id, cred_id=cred_id)
    return None

@router.put(
    "/{cred_id}",
    response_model=credential_schema.ModelCredentialRead,
    summary="Update a model credential"
)
def update_credential(
    cred_id: uuid.UUID,
    update_data: credential_schema.ModelCredentialUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Update a specific AI model credential.
    You must be the owner of the credential to update it.
    """
    service = CredentialService(db)
    updated_credential = service.update_credential(
        credential_id=cred_id,
        update_data=update_data,
        current_user=current_user
    )

    return credential_schema.ModelCredentialRead(
        **updated_credential.__dict__,
        masked_api_key=_mask_api_key(updated_credential.encrypted_api_key)
    )

@router.patch(
    "/{cred_id}/set-default",
    response_model=credential_schema.ModelCredentialRead,
    summary="Set a credential as default"
)
def set_default_credential(
    cred_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Set a specific AI model credential as the default for its type.
    You must be the owner of the credential to set it as default.
    """
    service = CredentialService(db)
    updated_credential = service.set_default_credential(
        credential_id=cred_id,
        current_user=current_user
    )

    return credential_schema.ModelCredentialRead(
        **updated_credential.__dict__,
        masked_api_key=_mask_api_key(updated_credential.encrypted_api_key)
    )
