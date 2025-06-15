from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.kb_auth import get_kb_or_public
from app.services.search_service import SearchService
from app.schemas.search import SearchQuery, SearchResponse, ChunkResponse
from app.models.user import User
from typing import Optional

router = APIRouter(prefix="/api/v1", tags=["search"])

@router.get("/chunks/{chunk_id}", response_model=ChunkResponse)
def get_chunk(
    chunk_id: str = Path(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """根据ID获取chunk"""
    search_service = SearchService(db)
    chunk = search_service.get_chunk_by_id(chunk_id)
    
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk不存在")
    
    # 解析tags
    import json
    tags = json.loads(chunk.tags) if chunk.tags else []
    
    return ChunkResponse(
        id=chunk.id,
        kb_id=chunk.kb_id,
        document_id=chunk.document_id,
        chunk_index=chunk.chunk_index,
        content=chunk.content,
        tags=tags,
        created_at=chunk.created_at
    )

@router.post("/kbs/{kb_id}/search", response_model=SearchResponse)
def search_knowledge_base(
    kb_id: str = Path(...),
    query: SearchQuery = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_kb_or_public)
):
    """在指定知识库中执行语义搜索"""
    search_service = SearchService(db)
    
    try:
        results = search_service.search(kb_id, query.query, query.top_k)
        return SearchResponse(**results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")