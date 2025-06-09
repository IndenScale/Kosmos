from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.orm import Session
from typing import List
import json

from db.database import get_db
from models.user import User
from schemas.knowledge_base import (
    KBCreate, KBUpdate, KBResponse, KBDetailResponse,
    KBMemberAdd, KBMemberResponse, TagDictionaryUpdate
)
from services.kb_service import KBService
from dependencies.auth import get_current_user
from dependencies.kb_auth import (
    get_kb_member, get_kb_admin_or_owner, get_kb_owner, get_kb_or_public
)

router = APIRouter(prefix="/api/v1/kbs", tags=["knowledge_bases"])

@router.post("/", response_model=KBResponse, status_code=status.HTTP_201_CREATED)
def create_knowledge_base(
    kb_data: KBCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建新知识库"""
    kb_service = KBService(db)
    kb = kb_service.create_kb(kb_data, current_user)  # 改为传入current_user对象

    # 解析tag_dictionary为字典格式

    response_data = KBResponse.from_orm(kb)
    if kb.tag_dictionary and type(kb.tag_dictionary) == str:
        response_data.tag_dictionary = json.loads(kb.tag_dictionary)
    else:
        response_data.tag_dictionary = {}
    return response_data

@router.get("/", response_model=List[KBResponse])
def list_my_knowledge_bases(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """列出我参与的知识库"""
    kb_service = KBService(db)
    kbs = kb_service.get_user_kbs(current_user.id)

    result = []
    for kb in kbs:
        # 确保tag_dictionary是字典格式
        if isinstance(kb.tag_dictionary, str):
            try:
                tag_dict = json.loads(kb.tag_dictionary) if kb.tag_dictionary else {}
            except (json.JSONDecodeError, TypeError):
                tag_dict = {}
        else:
            tag_dict = kb.tag_dictionary or {}
        
        # 手动构建响应对象，避免from_orm的类型验证问题
        kb_data = KBResponse(
            id=kb.id,
            name=kb.name,
            description=kb.description,
            owner_id=kb.owner_id,
            tag_dictionary=tag_dict,
            milvus_collection_id=kb.milvus_collection_id,
            is_public=kb.is_public,
            created_at=kb.created_at
        )
        result.append(kb_data)

    return result

@router.get("/{kb_id}", response_model=KBDetailResponse)
def get_knowledge_base(
    kb_id: str = Path(...),
    current_user: User = Depends(get_kb_or_public),
    db: Session = Depends(get_db)
):
    """获取知识库详情"""
    kb_service = KBService(db)
    kb = kb_service.get_kb_by_id(kb_id)

    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found"
        )

    # 获取成员列表
    members = kb_service.get_kb_members(kb_id)
    member_responses = []
    for member in members:
        member_data = {
            "user_id": member.user_id,
            "username": member.user.username,
            "email": member.user.email,
            "role": member.role,
            "created_at": member.created_at
        }
        member_responses.append(KBMemberResponse(**member_data))

    response_data = {
        "id": kb.id,
        "name": kb.name,
        "description": kb.description,
        "owner_id": kb.owner_id,
        "tag_dictionary": json.loads(kb.tag_dictionary) if kb.tag_dictionary else {},
        "is_public": kb.is_public,
        "created_at": kb.created_at,
        "members": member_responses,
        "owner_username": kb.owner.username
    }

    return KBDetailResponse(**response_data)

@router.put("/{kb_id}", response_model=KBResponse)
def update_knowledge_base(
    kb_data: KBUpdate,
    kb_id: str = Path(...),
    current_user: User = Depends(get_kb_admin_or_owner),
    db: Session = Depends(get_db)
):
    """更新知识库信息"""
    kb_service = KBService(db)
    kb = kb_service.update_kb(kb_id, kb_data)

    response_data = KBResponse.from_orm(kb)
    response_data.tag_dictionary = json.loads(kb.tag_dictionary) if kb.tag_dictionary else {}
    return response_data

@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_knowledge_base(
    kb_id: str = Path(...),
    current_user: User = Depends(get_kb_owner),
    db: Session = Depends(get_db)
):
    """删除知识库"""
    kb_service = KBService(db)
    kb_service.delete_kb(kb_id)

@router.put("/{kb_id}/tags", response_model=dict)
def update_tag_dictionary(
    tag_data: TagDictionaryUpdate,
    kb_id: str = Path(...),
    current_user: User = Depends(get_kb_owner),
    db: Session = Depends(get_db)
):
    """更新标签字典"""
    kb_service = KBService(db)
    kb = kb_service.update_tag_dictionary(kb_id, tag_data)

    return {
        "message": "Tag dictionary updated successfully",
        "tag_dictionary": json.loads(kb.tag_dictionary) if kb.tag_dictionary else {}
    }

@router.get("/{kb_id}/members", response_model=List[KBMemberResponse])
def get_knowledge_base_members(
    kb_id: str = Path(...),
    current_user: User = Depends(get_kb_admin_or_owner),
    db: Session = Depends(get_db)
):
    """获取知识库成员列表"""
    kb_service = KBService(db)
    members = kb_service.get_kb_members(kb_id)

    result = []
    for member in members:
        member_data = {
            "user_id": member.user_id,
            "username": member.user.username,
            "email": member.user.email,
            "role": member.role,
            "created_at": member.created_at
        }
        result.append(KBMemberResponse(**member_data))

    return result

@router.post("/{kb_id}/members", response_model=KBMemberResponse, status_code=status.HTTP_201_CREATED)
def add_knowledge_base_member(
    member_data: KBMemberAdd,
    kb_id: str = Path(...),
    current_user: User = Depends(get_kb_admin_or_owner),
    db: Session = Depends(get_db)
):
    """添加知识库成员"""
    kb_service = KBService(db)
    member = kb_service.add_member(kb_id, member_data)

    response_data = {
        "user_id": member.user_id,
        "username": member.user.username,
        "email": member.user.email,
        "role": member.role,
        "created_at": member.created_at
    }

    return KBMemberResponse(**response_data)

@router.delete("/{kb_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_knowledge_base_member(
    user_id: str,
    kb_id: str = Path(...),
    current_user: User = Depends(get_kb_admin_or_owner),
    db: Session = Depends(get_db)
):
    """移除知识库成员"""
    kb_service = KBService(db)
    kb_service.remove_member(kb_id, user_id)