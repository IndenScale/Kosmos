"""
Service layer for managing the link between Knowledge Spaces and Model Credentials.
"""
import uuid
from typing import List
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, status

from .. import models
from ..schemas import credential_link as credential_link_schema

class CredentialLinkService:
    def __init__(self, db: Session):
        self.db = db

    def _get_link_or_404(self, knowledge_space_id: uuid.UUID, credential_id: uuid.UUID) -> models.KnowledgeSpaceModelCredentialLink:
        """Fetches a specific link, raising a 404 if not found."""
        link = self.db.query(models.KnowledgeSpaceModelCredentialLink).filter_by(
            knowledge_space_id=knowledge_space_id,
            credential_id=credential_id
        ).first()
        if not link:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential link not found.")
        return link

    def link_credential(
        self,
        knowledge_space_id: uuid.UUID,
        link_in: credential_link_schema.CredentialLinkCreate,
        current_user: models.User
    ) -> models.KnowledgeSpaceModelCredentialLink:
        """Links a credential to a knowledge space."""
        # 1. Verify the credential exists and belongs to the current user
        credential = self.db.query(models.ModelCredential).filter_by(
            id=link_in.credential_id,
            owner_id=current_user.id
        ).first()
        if not credential:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Credential not found or you are not the owner."
            )

        # 2. Check if the link already exists
        existing_link = self.db.query(models.KnowledgeSpaceModelCredentialLink).filter_by(
            knowledge_space_id=knowledge_space_id,
            credential_id=link_in.credential_id
        ).first()
        if existing_link:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This credential is already linked to the knowledge space."
            )

        # 3. Create the new link
        new_link = models.KnowledgeSpaceModelCredentialLink(
            knowledge_space_id=knowledge_space_id,
            **link_in.model_dump()
        )
        self.db.add(new_link)
        self.db.commit()
        self.db.refresh(new_link)
        return new_link

    def get_linked_credentials(self, knowledge_space_id: uuid.UUID) -> List[models.KnowledgeSpaceModelCredentialLink]:
        """Lists all credentials linked to a knowledge space."""
        return self.db.query(models.KnowledgeSpaceModelCredentialLink).options(
            joinedload(models.KnowledgeSpaceModelCredentialLink.credential)
        ).filter_by(knowledge_space_id=knowledge_space_id).all()

    def update_credential_link(
        self,
        knowledge_space_id: uuid.UUID,
        credential_id: uuid.UUID,
        update_data: credential_link_schema.CredentialLinkUpdate
    ) -> models.KnowledgeSpaceModelCredentialLink:
        """Updates the properties (priority, weight) of a credential link."""
        link = self._get_link_or_404(knowledge_space_id, credential_id)
        
        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(link, key, value)
            
        self.db.commit()
        self.db.refresh(link)
        return link

    def unlink_credential(self, knowledge_space_id: uuid.UUID, credential_id: uuid.UUID):
        """Removes the link between a credential and a knowledge space."""
        link = self._get_link_or_404(knowledge_space_id, credential_id)
        self.db.delete(link)
        self.db.commit()
        return None
