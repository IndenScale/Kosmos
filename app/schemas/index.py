"""
索引相关的Pydantic模式
文件: index.py
创建时间: 2025-07-26
描述: 定义索引管理的请求和响应模式
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class IndexStatus(str, Enum):
    """索引状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class IndexRequest(BaseModel):
    """单个Fragment索引请求模式"""
    force_regenerate: bool = Field(False, description="是否强制重新生成索引")
    max_tags: int = Field(20, description="最大标签数量")
    # 为未来多模态索引预留字段
    enable_multimodal: bool = Field(False, description="是否启用多模态索引（预留字段）")
    multimodal_config: Optional[Dict[str, Any]] = Field(None, description="多模态索引配置（预留字段）")


class BatchIndexByFragmentsRequest(BaseModel):
    """基于Fragment ID的批量索引请求模式"""
    fragment_ids: List[str] = Field(..., description="要索引的Fragment ID列表")
    force_regenerate: bool = Field(False, description="是否强制重新生成索引")
    max_tags: int = Field(20, description="最大标签数量")
    # 为未来多模态索引预留字段
    enable_multimodal: bool = Field(False, description="是否启用多模态索引（预留字段）")
    multimodal_config: Optional[Dict[str, Any]] = Field(None, description="多模态索引配置（预留字段）")


class BatchIndexByDocumentsRequest(BaseModel):
    """基于Document ID的批量索引请求模式"""
    document_ids: List[str] = Field(..., description="要索引的文档ID列表")
    force_regenerate: bool = Field(False, description="是否强制重新生成索引")
    max_tags: int = Field(20, description="最大标签数量")
    # 为未来多模态索引预留字段
    enable_multimodal: bool = Field(False, description="是否启用多模态索引（预留字段）")
    multimodal_config: Optional[Dict[str, Any]] = Field(None, description="多模态索引配置（预留字段）")


# 保持向后兼容性的别名
BatchIndexRequest = BatchIndexByFragmentsRequest


class IndexResponse(BaseModel):
    """索引响应模式"""
    id: str = Field(..., description="索引ID")
    kb_id: str = Field(..., description="知识库ID")
    fragment_id: str = Field(..., description="Fragment ID")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    content: str = Field(..., description="索引内容")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True


class IndexJobResponse(BaseModel):
    """索引任务响应模式"""
    job_id: str = Field(..., description="任务ID")
    kb_id: str = Field(..., description="知识库ID")
    status: IndexStatus = Field(..., description="任务状态")
    total_fragments: int = Field(..., description="总Fragment数量")
    processed_fragments: int = Field(..., description="已处理Fragment数量")
    failed_fragments: int = Field(..., description="失败Fragment数量")
    error_message: Optional[str] = Field(None, description="错误信息")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class IndexStatsResponse(BaseModel):
    """索引统计信息响应模式"""
    kb_id: str = Field(..., description="知识库ID")
    total_fragments: int = Field(..., description="总Fragment数量")
    indexed_fragments: int = Field(..., description="已索引Fragment数量")
    pending_fragments: int = Field(..., description="待索引Fragment数量")
    vector_count: int = Field(..., description="向量数据库中的向量数量")
    last_index_time: Optional[datetime] = Field(None, description="最后索引时间")


class IndexProgressResponse(BaseModel):
    """索引进度响应模式"""
    job_id: str = Field(..., description="任务ID")
    status: IndexStatus = Field(..., description="任务状态")
    progress: float = Field(..., description="进度百分比 (0-100)")
    current_fragment: Optional[str] = Field(None, description="当前处理的Fragment ID")
    estimated_remaining_time: Optional[int] = Field(None, description="预计剩余时间（秒）")
    error_message: Optional[str] = Field(None, description="错误信息")