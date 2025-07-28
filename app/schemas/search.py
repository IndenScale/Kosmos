from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class FragmentType(str, Enum):
    """Fragment类型枚举"""
    TEXT = "text"
    SCREENSHOT = "screenshot"
    FIGURE = "figure"

class QueryParseResult(BaseModel):
    """查询解析结果"""
    text_query: str = Field(..., description="文本查询部分")
    must_tags: List[str] = Field(default_factory=list, description="必须包含的标签（+标记）")
    must_not_tags: List[str] = Field(default_factory=list, description="必须不包含的标签（-标记）")
    like_tags: List[str] = Field(default_factory=list, description="偏好标签（~标记）")
    original_query: str = Field(..., description="原始查询字符串")

class SearchQuery(BaseModel):
    """搜索查询请求"""
    query: str = Field(..., description="搜索查询字符串，支持标签语法：' +tag'（必须有）、' -tag'（必须没有）、' ~tag'（偏好）")
    top_k: int = Field(10, gt=0, le=50, description="最终返回的结果数量")
    fragment_types: List[FragmentType] = Field(default_factory=lambda: [FragmentType.TEXT], description="指定搜索的Fragment类型，默认只搜索text类型")
    must_tags: List[str] = Field(default_factory=list, description="必须包含的标签")
    must_not_tags: List[str] = Field(default_factory=list, description="必须不包含的标签")
    like_tags: List[str] = Field(default_factory=list, description="偏好标签（用于重排序）")
    parse_query: bool = Field(default=True, description="是否解析查询字符串中的标签语法")
    include_screenshots: bool = Field(default=False, description="是否包含相关页面范围内的截图")
    include_figures: bool = Field(default=False, description="是否包含相关页面范围内的插图")

class SearchResult(BaseModel):
    """搜索结果项"""
    fragment_id: str = Field(..., description="Fragment ID")
    document_id: str = Field(..., description="文档ID")
    fragment_type: str = Field(..., description="Fragment类型")
    content: str = Field(..., description="内容")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    score: float = Field(..., description="相似度分数")
    meta_info: Optional[Dict[str, Any]] = Field(None, description="Fragment元数据")
    source_file_name: Optional[str] = Field(None, description="原始文件名")
    figure_name: Optional[str] = Field(None, description="可读的片段名称")
    related_screenshots: Optional[List[Dict[str, Any]]] = Field(None, description="相关截图（可选）")
    related_figures: Optional[List[Dict[str, Any]]] = Field(None, description="相关插图（可选）")
    page_range: Optional[Dict[str, int]] = Field(None, description="页面范围信息（可选）")

    @field_validator('tags', mode='before')
    @classmethod
    def validate_tags(cls, v):
        """验证并清理tags字段"""
        if v is None:
            return []
        if isinstance(v, list):
            return [str(tag) for tag in v if tag is not None]
        return []

class SearchStats(BaseModel):
    """搜索统计信息"""
    original_count: int = Field(..., description="原始结果数量")
    deduplicated_count: int = Field(..., description="去重后结果数量")
    final_count: int = Field(..., description="最终返回结果数量")
    search_time_ms: Optional[float] = Field(None, description="搜索耗时（毫秒）")

class RecommendedTag(BaseModel):
    """推荐标签"""
    tag: str = Field(..., description="标签名称")
    count: int = Field(..., description="出现次数")
    relevance: float = Field(..., description="相关性分数")



class SearchResponse(BaseModel):
    """搜索响应"""
    results: List[SearchResult] = Field(..., description="搜索结果列表")
    recommended_tags: List[RecommendedTag] = Field(default_factory=list, description="推荐标签")
    stats: SearchStats = Field(..., description="搜索统计信息")
    query_parse_result: Optional[QueryParseResult] = Field(None, description="查询解析结果")

class FragmentDetailResponse(BaseModel):
    """Fragment详情响应"""
    fragment_id: str = Field(..., description="Fragment ID")
    kb_id: str = Field(..., description="知识库ID")
    document_id: str = Field(..., description="文档ID")
    fragment_index: int = Field(..., description="Fragment索引")
    fragment_type: str = Field(..., description="Fragment类型")
    content: str = Field(..., description="内容")
    raw_content: Optional[str] = Field(None, description="原始内容")
    meta_info: Optional[Dict[str, Any]] = Field(None, description="元数据信息")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    @field_validator('tags', mode='before')
    @classmethod
    def validate_tags(cls, v):
        """验证并清理tags字段"""
        if v is None:
            return []
        if isinstance(v, list):
            return [str(tag) for tag in v if tag is not None]
        return []

    class Config:
        from_attributes = True