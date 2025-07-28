"""
模型访问凭证管理路由
文件: credentials.py
创建时间: 2025-07-26
描述: 提供凭证和知识库模型配置的API接口
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.credential import ModelType
from app.services.credential_service import credential_service
from app.schemas.credential import (
    CredentialCreate, CredentialUpdate, CredentialResponse, CredentialListResponse,
    KBModelConfigCreate, KBModelConfigUpdate, KBModelConfigResponse, KBModelConfigsResponse,
    ModelTypesResponse
)

router = APIRouter(prefix="/api/v1/credentials", tags=["credentials"])


@router.get("/model-types", response_model=ModelTypesResponse)
async def get_model_types():
    """获取支持的模型类型列表"""
    return ModelTypesResponse.get_default()


@router.post("/", response_model=CredentialResponse, status_code=status.HTTP_201_CREATED)
async def create_credential(
    credential_data: CredentialCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建新的模型访问凭证"""
    try:
        credential = credential_service.create_credential(
            db=db,
            user_id=current_user.id,
            credential_data=credential_data
        )

        # 构造响应，隐藏敏感信息
        api_key_display = credential_service.get_api_key_display(credential.api_key_encrypted)
        response_data = CredentialResponse(
            id=credential.id,
            user_id=credential.user_id,
            name=credential.name,
            provider=credential.provider,
            model_type=credential.model_type,
            base_url=credential.base_url,
            description=credential.description,
            api_key_encrypted=credential.api_key_encrypted,
            api_key_display=api_key_display,
            is_active=credential.is_active,
            created_at=credential.created_at,
            updated_at=credential.updated_at
        )

        return response_data

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建凭证失败: {str(e)}"
        )


@router.get("/", response_model=CredentialListResponse)
async def get_user_credentials(
    model_type: Optional[ModelType] = Query(None, description="按模型类型筛选"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取当前用户的所有凭证"""
    try:
        credentials = credential_service.get_user_credentials(
            db=db,
            user_id=current_user.id,
            model_type=model_type
        )

        # 构造响应数据
        credential_responses = []
        for cred in credentials:
            api_key_display = credential_service.get_api_key_display(cred.api_key_encrypted)
            credential_responses.append(CredentialResponse(
                id=cred.id,
                user_id=cred.user_id,
                name=cred.name,
                provider=cred.provider,
                model_type=cred.model_type,
                base_url=cred.base_url,
                description=cred.description,
                api_key_encrypted=cred.api_key_encrypted,
                api_key_display=api_key_display,
                is_active=cred.is_active,
                created_at=cred.created_at,
                updated_at=cred.updated_at
            ))

        return CredentialListResponse(
            credentials=credential_responses,
            total=len(credential_responses)
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取凭证列表失败: {str(e)}"
        )


@router.get("/{credential_id}", response_model=CredentialResponse)
async def get_credential(
    credential_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取指定的凭证详情"""
    credential = credential_service.get_credential_by_id(
        db=db,
        credential_id=credential_id,
        user_id=current_user.id
    )

    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="凭证不存在或无权限访问"
        )

    api_key_display = credential_service.get_api_key_display(credential.api_key_encrypted)
    return CredentialResponse(
        id=credential.id,
        user_id=credential.user_id,
        name=credential.name,
        provider=credential.provider,
        model_type=credential.model_type,
        base_url=credential.base_url,
        description=credential.description,
        api_key_encrypted=credential.api_key_encrypted,
        api_key_display=api_key_display,
        is_active=credential.is_active,
        created_at=credential.created_at,
        updated_at=credential.updated_at
    )


@router.put("/{credential_id}", response_model=CredentialResponse)
async def update_credential(
    credential_id: str,
    credential_data: CredentialUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新凭证"""
    try:
        credential = credential_service.update_credential(
            db=db,
            credential_id=credential_id,
            user_id=current_user.id,
            credential_data=credential_data
        )

        if not credential:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="凭证不存在或无权限访问"
            )

        api_key_display = credential_service.get_api_key_display(credential.api_key_encrypted)
        return CredentialResponse(
            id=credential.id,
            user_id=credential.user_id,
            name=credential.name,
            provider=credential.provider,
            model_type=credential.model_type,
            base_url=credential.base_url,
            description=credential.description,
            api_key_encrypted=credential.api_key_encrypted,
            api_key_display=api_key_display,
            is_active=credential.is_active,
            created_at=credential.created_at,
            updated_at=credential.updated_at
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新凭证失败: {str(e)}"
        )


@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    credential_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除凭证"""
    try:
        success = credential_service.delete_credential(
            db=db,
            credential_id=credential_id,
            user_id=current_user.id
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="凭证不存在或无权限访问"
            )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除凭证失败: {str(e)}"
        )


# 知识库模型配置相关接口
@router.post("/kb-configs", response_model=KBModelConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_kb_model_config(
    config_data: KBModelConfigCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """为知识库创建模型配置"""
    try:
        config = credential_service.create_kb_model_config(
            db=db,
            config_data=config_data,
            user_id=current_user.id
        )

        return credential_service.get_kb_model_config_response(db, config, current_user.id)
    except Exception as e:
        # logger.error(f"创建知识库模型配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建知识库模型配置失败: {str(e)}")


@router.get("/kb-configs/{kb_id}", response_model=KBModelConfigsResponse)
async def get_kb_model_configs(
    kb_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取知识库的所有模型配置"""
    try:
        return credential_service.get_kb_model_configs_response(db, kb_id, current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取模型配置失败: {str(e)}"
        )


@router.put("/kb-configs/{config_id}", response_model=KBModelConfigResponse)
async def update_kb_model_config(
    config_id: str,
    config_data: KBModelConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新知识库模型配置"""
    try:
        # 先获取凭证信息以确定模型类型
        credential = credential_service.get_credential_by_id(
            db=db,
            credential_id=config_data.credential_id,
            user_id=current_user.id
        )

        if not credential:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="凭证不存在或无权限访问"
            )

        config = credential_service.update_kb_model_config(
            db=db,
            config_id=config_id,
            user_id=current_user.id,
            config_data=config_data
        )

        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="模型配置不存在或无权限访问"
            )

        # 传递更新的模型类型，确保返回正确的配置
        return credential_service.get_kb_model_config_response(
            db, config, current_user.id, preferred_model_type=credential.model_type
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新模型配置失败: {str(e)}"
        )


@router.delete("/kb-configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_kb_model_config(
    config_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除知识库模型配置"""
    try:
        success = credential_service.delete_kb_model_config(
            db=db,
            config_id=config_id,
            user_id=current_user.id
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="模型配置不存在或无权限访问"
            )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除模型配置失败: {str(e)}"
        )