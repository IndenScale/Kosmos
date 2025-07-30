"""
Fragment相关的路由
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies.kb_auth import get_kb_member, get_kb_or_public
from app.services.fragment_service import FragmentService
from app.schemas.fragment import (
    FragmentResponse, 
    FragmentListResponse, 
    FragmentUpdate,
    FragmentStatsResponse
)

router = APIRouter(prefix="/api/v1", tags=["fragments"])


@router.get("/kbs/{kb_id}/fragments", response_model=FragmentListResponse)
def get_kb_fragments(
    kb_id: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    fragment_type: Optional[str] = Query(None, description="Fragment类型过滤"),
    db: Session = Depends(get_db),
    current_user=Depends(get_kb_or_public)
):
    """获取知识库的Fragment列表"""
    fragment_service = FragmentService(db)
    return fragment_service.get_kb_fragments(
        kb_id=kb_id,
        page=page,
        page_size=page_size,
        fragment_type=fragment_type
    )


@router.get("/documents/{document_id}/fragments", response_model=List[FragmentResponse])
def get_document_fragments(
    document_id: str,
    db: Session = Depends(get_db)
):
    """获取文档的Fragment列表"""
    fragment_service = FragmentService(db)
    return fragment_service.get_document_fragments(document_id)


@router.get("/fragments/{fragment_id}", response_model=FragmentResponse)
def get_fragment(
    fragment_id: str,
    db: Session = Depends(get_db)
):
    """获取Fragment详情"""
    fragment_service = FragmentService(db)
    fragment = fragment_service.get_fragment(fragment_id)
    if not fragment:
        raise HTTPException(status_code=404, detail="Fragment not found")
    return fragment


@router.put("/fragments/{fragment_id}", response_model=FragmentResponse)
def update_fragment(
    fragment_id: str,
    fragment_update: FragmentUpdate,
    db: Session = Depends(get_db)
):
    """更新Fragment"""
    fragment_service = FragmentService(db)
    fragment = fragment_service.update_fragment(fragment_id, fragment_update)
    if not fragment:
        raise HTTPException(status_code=404, detail="Fragment not found")
    return fragment


@router.delete("/fragments/{fragment_id}")
def delete_fragment(
    fragment_id: str,
    db: Session = Depends(get_db)
):
    """删除Fragment"""
    fragment_service = FragmentService(db)
    success = fragment_service.delete_fragment(fragment_id)
    if not success:
        raise HTTPException(status_code=404, detail="Fragment not found")
    return {"message": "Fragment deleted successfully"}


@router.get("/kbs/{kb_id}/fragments/stats", response_model=FragmentStatsResponse)
def get_kb_fragment_stats(
    kb_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_kb_or_public)
):
    """获取知识库Fragment统计信息"""
    fragment_service = FragmentService(db)
    return fragment_service.get_kb_fragment_stats(kb_id)