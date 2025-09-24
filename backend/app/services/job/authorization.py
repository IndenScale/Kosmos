"""权限验证模块，用于处理Job相关的访问控制逻辑。"""
import uuid
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import HTTPException, status

from backend.app.models import User, Document, KnowledgeSpace, KnowledgeSpaceMember


def verify_knowledge_space_access(db: Session, user: User, knowledge_space_id: uuid.UUID) -> bool:
    """验证用户是否有访问指定知识空间的权限。"""
    user_has_access = db.query(KnowledgeSpace.id).outerjoin(
        KnowledgeSpaceMember, 
        KnowledgeSpace.id == KnowledgeSpaceMember.knowledge_space_id
    ).filter(
        KnowledgeSpace.id == knowledge_space_id,
        or_(
            KnowledgeSpace.owner_id == user.id,
            KnowledgeSpaceMember.user_id == user.id
        )
    ).first()
    
    return user_has_access is not None


def verify_document_access_and_get_ks_id(db: Session, user: User, document_id: uuid.UUID) -> uuid.UUID:
    """验证用户对文档的访问权限，并返回文档所属的知识空间ID。"""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    
    if not verify_knowledge_space_access(db, user, doc.knowledge_space_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have access to the document's knowledge space"
        )
    
    return doc.knowledge_space_id


def verify_job_list_access(
    db: Session, 
    user: User, 
    knowledge_space_id: Optional[uuid.UUID] = None,
    document_id: Optional[uuid.UUID] = None
) -> Optional[uuid.UUID]:
    """验证用户对job列表的访问权限，返回需要检查的知识空间ID。"""
    ks_id_to_check = knowledge_space_id
    
    if document_id:
        doc_ks_id = verify_document_access_and_get_ks_id(db, user, document_id)
        
        if not ks_id_to_check:
            ks_id_to_check = doc_ks_id
        elif ks_id_to_check != doc_ks_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The provided document_id does not belong to the specified knowledge_space_id."
            )
    
    # 如果涉及知识空间，执行权限检查
    if ks_id_to_check:
        if not verify_knowledge_space_access(db, user, ks_id_to_check):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have access to the specified knowledge space."
            )
    
    return ks_id_to_check


def verify_job_access(db: Session, user: User, job_knowledge_space_id: uuid.UUID) -> None:
    """验证用户对特定job的访问权限。"""
    if not verify_knowledge_space_access(db, user, job_knowledge_space_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have access to the knowledge space of this job"
        )