from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class SearchQuery(BaseModel):
    query: str = Field(..., description="复合查询字符串，例如：'AI未来发展 +技术 -历史 ~应用'")
    top_k: int = Field(10, gt=0, le=50, description="最终返回的结果数量")

class SearchResult(BaseModel):
    chunk_id: str
    document_id: str
    content: str
    tags: List[str]
    score: float

class RecommendedTag(BaseModel):
    tag: str
    freq: int
    eig_score: float

class SearchResponse(BaseModel):
    results: List[SearchResult]
    recommended_tags: List[RecommendedTag]

class ChunkResponse(BaseModel):
    id: str
    kb_id: str
    document_id: str
    chunk_index: int
    content: str
    tags: List[str]
    created_at: datetime
    
    class Config:
        from_attributes = True