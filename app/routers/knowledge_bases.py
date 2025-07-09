from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.orm import Session
from typing import List
import json

from app.db.database import get_db
from app.models.user import User
from app.schemas.knowledge_base import (
    KBCreate, KBUpdate, KBResponse, KBDetailResponse,
    KBMemberAdd, KBMemberResponse, TagDictionaryUpdate
)
from app.services.kb_service import KBService
from app.dependencies.auth import get_current_user
from app.dependencies.kb_auth import (
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
    kb = kb_service.create_kb(kb_data, current_user)

    response_data = KBResponse.model_validate(kb)
    if kb.tag_dictionary:
        if type(kb.tag_dictionary) == str:
            response_data.tag_dictionary = json.loads(kb.tag_dictionary)
        elif type(kb.tag_dictionary) == dict:
            response_data.tag_dictionary = kb.tag_dictionary
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
        if isinstance(kb.tag_dictionary, str):
            try:
                tag_dict = kb.tag_dictionary
            except (json.JSONDecodeError, TypeError):
                tag_dict = {}
        else:
            tag_dict = kb.tag_dictionary or {}

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

    members = kb_service.get_kb_members(kb_id)
    member_responses = []
    for member in members:
        member_data = {
            "user_id": member.user_id,
            "username": member.user.username,
            "email": member.user.email,
            "role": member.role,
            "created_at": member.created_at  # 修复：joined_at -> created_at
        }
        member_responses.append(KBMemberResponse(**member_data))

    if isinstance(kb.tag_dictionary, str):
        try:
            tag_dict = json.loads(kb.tag_dictionary) if kb.tag_dictionary else {}
        except (json.JSONDecodeError, TypeError):
            tag_dict = {}
    else:
        tag_dict = kb.tag_dictionary or {}

    return KBDetailResponse(
        id=kb.id,
        name=kb.name,
        description=kb.description,
        owner_id=kb.owner_id,
        owner_username=kb.owner.username,  # 添加缺失的 owner_username 字段
        tag_dictionary=tag_dict,
        milvus_collection_id=kb.milvus_collection_id,
        is_public=kb.is_public,
        created_at=kb.created_at,
        last_tag_directory_update_time=kb.last_tag_directory_update_time,
        members=member_responses
    )

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
    return KBResponse.model_validate(kb)

@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_knowledge_base(
    kb_id: str = Path(...),
    current_user: User = Depends(get_kb_owner),
    db: Session = Depends(get_db)
):
    """删除知识库"""
    kb_service = KBService(db)
    success = kb_service.delete_kb(kb_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found"
        )

@router.put("/{kb_id}/tags", response_model=KBResponse)
def update_tag_dictionary(
    tag_data: TagDictionaryUpdate,
    kb_id: str = Path(...),
    current_user: User = Depends(get_kb_admin_or_owner),
    db: Session = Depends(get_db)
):
    """更新标签字典"""
    kb_service = KBService(db)
    kb = kb_service.update_tag_dictionary(kb_id, tag_data)
    return KBResponse.model_validate(kb)

@router.get("/{kb_id}/members", response_model=List[KBMemberResponse])
def get_knowledge_base_members(
    kb_id: str = Path(...),
    current_user: User = Depends(get_kb_member),
    db: Session = Depends(get_db)
):
    """获取知识库成员列表"""
    kb_service = KBService(db)
    members = kb_service.get_kb_members(kb_id)

    return [KBMemberResponse(
        user_id=member.user_id,
        username=member.user.username,
        role=member.role,
        joined_at=member.joined_at
    ) for member in members]

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

    return KBMemberResponse(
        user_id=member.user_id,
        username=member.user.username,
        role=member.role,
        joined_at=member.joined_at
    )

@router.delete("/{kb_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_knowledge_base_member(
    kb_id: str = Path(...),
    user_id: str = Path(...),
    current_user: User = Depends(get_kb_admin_or_owner),
    db: Session = Depends(get_db)
):
    """移除知识库成员"""
    kb_service = KBService(db)
    success = kb_service.remove_member(kb_id, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found"
        )

@router.get("/{kb_id}/stats")
def get_knowledge_base_stats(
    kb_id: str = Path(...),
    current_user: User = Depends(get_kb_member),
    db: Session = Depends(get_db)
):
    """获取知识库统计信息"""
    kb_service = KBService(db)
    return kb_service.get_kb_stats(kb_id)