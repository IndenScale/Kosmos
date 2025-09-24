import uuid
from typing import List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from .. import models
from ..schemas.credential import ModelCredentialCreate, ModelCredentialUpdate
from ..core.security import encrypt_api_key

class CredentialService:
    def __init__(self, db: Session):
        self.db = db

    def create_credential(
        self,
        owner_id: uuid.UUID,
        cred_in: ModelCredentialCreate
    ) -> models.ModelCredential:
        """
        创建新的模型凭证
        """
        # 处理API密钥加密
        encrypted_api_key = None
        if cred_in.api_key:
            encrypted_api_key = encrypt_api_key(cred_in.api_key)

        # 如果设置为默认，需要取消同类型的其他默认凭证
        if cred_in.is_default:
            self.db.query(models.ModelCredential).filter(
                models.ModelCredential.owner_id == owner_id,
                models.ModelCredential.credential_type == cred_in.credential_type,
                models.ModelCredential.is_default == True
            ).update({"is_default": False})

        # 创建新凭证
        db_credential = models.ModelCredential(
            owner_id=owner_id,
            credential_type=cred_in.credential_type,
            model_family=cred_in.model_family,
            provider=cred_in.provider,
            model_name=cred_in.model_name,
            base_url=cred_in.base_url,
            encrypted_api_key=encrypted_api_key,
            is_default=cred_in.is_default
        )

        self.db.add(db_credential)
        self.db.commit()
        self.db.refresh(db_credential)
        return db_credential

    def get_user_credentials(self, user_id: uuid.UUID) -> List[models.ModelCredential]:
        """
        获取用户的所有凭证
        """
        return self.db.query(models.ModelCredential).filter(
            models.ModelCredential.owner_id == user_id
        ).all()

    def get_credential_by_id(self, credential_id: uuid.UUID) -> models.ModelCredential:
        """Fetches a credential by its ID."""
        credential = self.db.query(models.ModelCredential).filter(models.ModelCredential.id == credential_id).first()
        if not credential:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found")
        return credential

    def update_credential(
        self,
        credential_id: uuid.UUID,
        update_data: ModelCredentialUpdate,
        current_user: models.User
    ) -> models.ModelCredential:
        """Updates a credential for the current user."""
        credential = self.get_credential_by_id(credential_id)

        # Authorization: Ensure the user owns the credential
        if str(credential.owner_id) != str(current_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update this credential")

        update_dict = update_data.dict(exclude_unset=True)

        # Handle API key encryption
        if "api_key" in update_dict and update_dict["api_key"] is not None:
            credential.encrypted_api_key = encrypt_api_key(update_dict["api_key"])

        # Remove api_key from update_dict only if it exists
        if "api_key" in update_dict:
            del update_dict["api_key"]

        # Handle 'is_default' uniqueness
        if update_dict.get("is_default") is True:
            # Find any other default credential of the same type and unset it
            self.db.query(models.ModelCredential).filter(
                models.ModelCredential.owner_id == current_user.id,
                models.ModelCredential.credential_type == credential.credential_type,
                models.ModelCredential.is_default == True,
                models.ModelCredential.id != credential_id
            ).update({"is_default": False})

        # Apply other updates
        for key, value in update_dict.items():
            setattr(credential, key, value)

        self.db.commit()
        self.db.refresh(credential)
        return credential

    def delete_credential(self, user_id: uuid.UUID, cred_id: uuid.UUID) -> None:
        """
        删除用户的凭证
        """
        credential = self.db.query(models.ModelCredential).filter(
            models.ModelCredential.id == cred_id,
            models.ModelCredential.owner_id == user_id
        ).first()

        if not credential:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Credential not found or not authorized"
            )

        self.db.delete(credential)
        self.db.commit()

    def set_default_credential(
        self,
        credential_id: uuid.UUID,
        current_user: models.User
    ) -> models.ModelCredential:
        """
        设置指定凭证为默认凭证
        """
        credential = self.get_credential_by_id(credential_id)

        # 权限检查：确保用户拥有该凭证
        if str(credential.owner_id) != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Not authorized to modify this credential"
            )

        # 取消同类型的其他默认凭证
        self.db.query(models.ModelCredential).filter(
            models.ModelCredential.owner_id == current_user.id,
            models.ModelCredential.credential_type == credential.credential_type,
            models.ModelCredential.is_default == True,
            models.ModelCredential.id != credential_id
        ).update({"is_default": False})

        # 设置当前凭证为默认
        credential.is_default = True
        
        self.db.commit()
        self.db.refresh(credential)
        return credential