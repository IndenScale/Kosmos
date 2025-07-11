from pydantic import BaseModel, Field, validator
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
    screenshot_ids: Optional[List[str]] = Field(default=None, description="关联的页面截图ID列表")
    
    @validator('screenshot_ids', pre=True)
    def validate_screenshot_ids(cls, v):
        """验证并清理screenshot_ids字段"""
        if v is None:
            return None
        if isinstance(v, list):
            # 过滤掉None值和非字符串值
            return [item for item in v if item is not None and isinstance(item, str)]
        return []

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
    screenshot_ids: Optional[List[str]] = Field(default=None, description="关联的页面截图ID列表")
    created_at: datetime
    
    @validator('screenshot_ids', pre=True)
    def validate_screenshot_ids(cls, v):
        """验证并清理screenshot_ids字段"""
        if v is None:
            return None
        if isinstance(v, list):
            # 过滤掉None值和非字符串值
            return [item for item in v if item is not None and isinstance(item, str)]
        return []
    
    class Config:
        from_attributes = True