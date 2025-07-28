"""
Fragment相关的Pydantic模式
文件: fragment.py
创建时间: 2025-07-26
描述: 定义fragment管理的请求和响应模式
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from enum import Enum


class FragmentType(str, Enum):
    """Fragment类型枚举"""
    TEXT = "text"
    SCREENSHOT = "screenshot"
    FIGURE = "figure"


class FragmentResponse(BaseModel):
    """Fragment响应模式"""
    id: str = Field(..., description="Fragment ID")
    content_hash: str = Field(..., description="物理文档内容哈希")
    document_id: str = Field(..., description="文档ID")
    fragment_index: int = Field(..., description="Fragment索引")
    fragment_type: FragmentType = Field(..., description="Fragment类型")
    raw_content: Optional[str] = Field(None, description="原始内容")
    meta_info: Optional[Dict[str, Any]] = Field(None, description="元数据信息")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True


class FragmentListResponse(BaseModel):
    """Fragment列表响应模式"""
    fragments: List[FragmentResponse] = Field(..., description="Fragment列表")
    total: int = Field(..., description="总数量")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页大小")


class FragmentUpdate(BaseModel):
    """Fragment更新请求模式（仅允许有限修改）"""
    meta_info: Optional[Dict[str, Any]] = Field(None, description="元数据信息")

    @field_validator('meta_info')
    @classmethod
    def validate_meta_info(cls, v):
        """验证meta_info，只允许修改特定字段"""
        if v is not None:
            # 只允许修改activated字段
            allowed_fields = {'activated'}
            if not set(v.keys()).issubset(allowed_fields):
                raise ValueError(f'只允许修改以下字段: {allowed_fields}')
        return v


class KBFragmentResponse(BaseModel):
    """知识库Fragment关联响应模式"""
    kb_id: str = Field(..., description="知识库ID")
    fragment_id: str = Field(..., description="Fragment ID")
    added_at: datetime = Field(..., description="添加时间")
    fragment: FragmentResponse = Field(..., description="Fragment详情")

    class Config:
        from_attributes = True


class FragmentStatsResponse(BaseModel):
    """Fragment统计信息响应模式"""
    kb_id: str = Field(..., description="知识库ID")
    total_fragments: int = Field(..., description="总Fragment数量")
    text_fragments: int = Field(..., description="文本Fragment数量")
    screenshot_fragments: int = Field(..., description="截图Fragment数量")
    figure_fragments: int = Field(..., description="插图Fragment数量")
    activated_fragments: int = Field(..., description="激活的Fragment数量")
    last_updated: Optional[datetime] = Field(None, description="最后更新时间")