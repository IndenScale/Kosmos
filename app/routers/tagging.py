from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any

from app.db.database import get_db
from app.services.tagging_service import TaggingService
from app.dependencies.auth import get_current_user
from app.dependencies.kb_auth import verify_kb_access
from app.models.user import User

router = APIRouter(
    prefix="/api/v1/tagging",
    tags=["tagging"]
)


@router.post("/{kb_id}/tag-chunks")
async def tag_chunks(
    kb_id: str,
    chunk_ids: Optional[List[str]] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_kb_access)
):
    """为指定的chunks生成标签"""
    try:
        tagging_service = TaggingService(db)
        result = tagging_service.tag_chunks(kb_id, chunk_ids)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"标签生成失败: {str(e)}"
        )


@router.post("/{kb_id}/tag-document/{document_id}")
async def tag_document(
    kb_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_kb_access)
):
    """为指定文档的所有chunks生成标签"""
    try:
        tagging_service = TaggingService(db)
        result = tagging_service.batch_tag_document(kb_id, document_id)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文档标签生成失败: {str(e)}"
        )


@router.get("/{kb_id}/stats")
async def get_tagging_stats(
    kb_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_kb_access)
):
    """获取知识库的标注统计信息"""
    try:
        tagging_service = TaggingService(db)
        stats = tagging_service.get_tagging_stats(kb_id)
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取标注统计失败: {str(e)}"
        )


@router.get("/{kb_id}/untagged-chunks")
async def get_untagged_chunks(
    kb_id: str,
    limit: Optional[int] = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_kb_access)
):
    """获取未标注的chunks列表"""
    try:
        from app.repositories.chunk_repo import ChunkRepository
        
        chunk_repo = ChunkRepository(db)
        untagged_chunks = chunk_repo.get_untagged_chunks(kb_id)
        
        if limit:
            untagged_chunks = untagged_chunks[:limit]
        
        # 转换为简化的响应格式
        chunks_data = []
        for chunk in untagged_chunks:
            chunks_data.append({
                "id": chunk.id,
                "content": chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content,
                "chunk_index": chunk.chunk_index,
                "document_id": chunk.document_id
            })
        
        return {
            "total_untagged": len(chunk_repo.get_untagged_chunks(kb_id)),
            "chunks": chunks_data
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取未标注chunks失败: {str(e)}"
        ) 