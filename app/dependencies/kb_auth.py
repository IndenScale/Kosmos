from fastapi import Depends, HTTPException, status, Path
from sqlalchemy.orm import Session
from typing import List

from app.db.database import get_db
from app.models.user import User
from app.models.knowledge_base import KBMember, KnowledgeBase, KBRole
from app.dependencies.auth import get_current_user

def get_kb_member_role(kb_id: str, user_id: str, db: Session) -> str:
    """获取用户在知识库中的角色"""
    member = db.query(KBMember).filter(
        KBMember.kb_id == kb_id,
        KBMember.user_id == user_id
    ).first()
    return member.role if member else None

def get_kb_member(
    kb_id: str = Path(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """检查用户是否为知识库成员"""
    role = get_kb_member_role(kb_id, current_user.id, db)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not a member of this knowledge base"
        )
    return current_user

def get_kb_admin_or_owner(
    kb_id: str = Path(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """检查用户是否为知识库管理员或拥有者"""
    role = get_kb_member_role(kb_id, current_user.id, db)
    # if role not in [KBRole.ADMIN.value, KBRole.OWNER.value]:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="User does not have Admin or Owner privileges for this KB"
    #     )
    return current_user

def get_kb_owner(
    kb_id: str = Path(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """检查用户是否为知识库拥有者"""
    role = get_kb_member_role(kb_id, current_user.id, db)
    # if role != KBRole.OWNER.value:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="User does not have Owner privileges for this KB"
    #     )
    return current_user

def get_kb_or_public(
    kb_id: str = Path(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """检查用户是否为知识库成员或知识库是否公开"""
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found"
        )

    if kb.is_public:
        return current_user

    role = get_kb_member_role(kb_id, current_user.id, db)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Knowledge base is private and user is not a member"
        )
    return current_user