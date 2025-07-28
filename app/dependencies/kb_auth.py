from fastapi import Depends, HTTPException, status, Path
from sqlalchemy.orm import Session
from typing import List, Optional, Literal

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


def check_kb_permission(
    kb_id: str,
    user: User,
    db: Session,
    required_role: Optional[Literal["member", "admin", "owner"]] = None,
    allow_public: bool = False,
    allow_system_admin: bool = True
) -> bool:
    """
    统一的权限检查函数
    
    Args:
        kb_id: 知识库ID
        user: 当前用户
        db: 数据库会话
        required_role: 要求的角色级别 ('member', 'admin', 'owner')
        allow_public: 是否允许公开知识库访问
        allow_system_admin: 是否允许系统管理员访问
    
    Returns:
        bool: 是否有权限
    """
    # 系统管理员权限检查
    if allow_system_admin and user.role == "system_admin":
        return True
    
    # 获取知识库信息
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
    if not kb:
        return False
    
    # 公开知识库检查
    if allow_public and kb.is_public:
        return True
    
    # 获取用户角色
    user_role = get_kb_member_role(kb_id, user.id, db)
    if not user_role:
        return False
    
    # 角色权限检查
    if required_role == "owner" and user_role != KBRole.OWNER.value:
        return False
    elif required_role == "admin" and user_role not in [KBRole.ADMIN.value, KBRole.OWNER.value]:
        return False
    elif required_role == "member" and user_role not in [KBRole.MEMBER.value, KBRole.ADMIN.value, KBRole.OWNER.value]:
        return False
    
    return True

def get_kb_member(
    kb_id: str = Path(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """检查用户是否为知识库成员"""
    if not check_kb_permission(kb_id, current_user, db, required_role="member"):
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
    if not check_kb_permission(kb_id, current_user, db, required_role="admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have Admin or Owner privileges for this KB"
        )
    return current_user

def get_kb_owner(
    kb_id: str = Path(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """检查用户是否为知识库拥有者"""
    if not check_kb_permission(kb_id, current_user, db, required_role="owner"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have Owner privileges for this KB"
        )
    return current_user

def get_kb_or_public(
    kb_id: str = Path(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """检查用户是否为知识库成员或知识库是否公开"""
    if not check_kb_permission(kb_id, current_user, db, allow_public=True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Knowledge base is private and user is not a member"
        )
    return current_user

def get_kb_document_access(
    kb_id: str = Path(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """检查用户是否有权限上传/下载知识库文档（KB成员或超级管理员）"""
    if not check_kb_permission(kb_id, current_user, db, required_role="member"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have access to this knowledge base documents"
        )
    return current_user

def verify_kb_access(
    kb_id: str = Path(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """验证用户对知识库的访问权限（通用权限检查）"""
    if not check_kb_permission(kb_id, current_user, db, required_role="member"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not a member of this knowledge base"
        )
    return None  # 返回None表示验证通过，用作依赖项

def get_document_kb_access(
    document_id: str = Path(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """通过文档ID验证用户对知识库的访问权限
    
    超级管理员可以访问所有文档
    知识库所有者和管理员可以访问其知识库的文档
    知识库成员在公开知识库中可以访问文档
    """
    from app.models.document import KBDocument
    
    # 获取文档对应的知识库
    kb_document = db.query(KBDocument).filter(
        KBDocument.document_id == document_id
    ).first()
    
    if not kb_document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在或未关联到知识库"
        )
    
    kb_id = kb_document.kb_id
    
    # 使用统一权限检查
    if not check_kb_permission(
        kb_id, 
        current_user, 
        db, 
        required_role="member",
        allow_public=True
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户没有权限访问此知识库的文档"
        )
    
    return kb_id