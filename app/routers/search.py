from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.kb_auth import get_kb_or_public
from app.services.search_service import SearchService
from app.schemas.search import SearchQuery, SearchResponse, ChunkResponse
from app.models.user import User
from typing import Optional
import json

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
    tags_str = getattr(chunk, 'tags', None)
    tags = json.loads(tags_str) if tags_str else []
    
    # 解析screenshot_ids
    screenshot_ids = []
    screenshot_ids_str = getattr(chunk, 'page_screenshot_ids', None)
    if screenshot_ids_str:
        try:
            screenshot_ids = json.loads(screenshot_ids_str)
        except json.JSONDecodeError:
            screenshot_ids = []
    
    return ChunkResponse(
        id=getattr(chunk, 'id'),
        kb_id=getattr(chunk, 'kb_id'),
        document_id=getattr(chunk, 'document_id'),
        chunk_index=getattr(chunk, 'chunk_index'),
        content=getattr(chunk, 'content'),
        tags=tags,
        screenshot_ids=screenshot_ids,
        created_at=getattr(chunk, 'created_at')
    )

@router.post("/kbs/{kb_id}/search", response_model=SearchResponse)
def search_knowledge_base(
    query: SearchQuery,
    kb_id: str = Path(...),
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