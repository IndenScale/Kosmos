"""
解析器相关的Pydantic模式
文件: parser.py
创建时间: 2025-07-26
描述: 定义文档解析的请求和响应模式
"""

from typing import Optional, List, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class DocumentParseRequest(BaseModel):
    """文档解析请求模式"""
    document_id: str = Field(..., description="文档ID")
    force_reparse: bool = Field(False, description="是否强制重新解析")


class BatchParseRequest(BaseModel):
    """批量解析请求模式"""
    document_ids: List[str] = Field(..., description="文档ID列表")
    force_reparse: bool = Field(False, description="是否强制重新解析")
    max_concurrent: int = Field(3, ge=1, le=10, description="最大并发数")


class ParseResponse(BaseModel):
    """解析响应模式"""
    document_id: str = Field(..., description="文档ID")
    total_fragments: int = Field(..., description="总Fragment数量")
    text_fragments: int = Field(..., description="文本Fragment数量")
    screenshot_fragments: int = Field(..., description="截图Fragment数量")
    figure_fragments: int = Field(..., description="插图Fragment数量")
    parse_duration_ms: int = Field(..., description="解析耗时（毫秒）")
    success: bool = Field(..., description="解析是否成功")
    error_message: Optional[str] = Field(None, description="错误信息")


class BatchParseResponse(BaseModel):
    """批量解析响应模式"""
    total_documents: int = Field(..., description="总文档数量")
    successful_parses: int = Field(..., description="成功解析数量")
    failed_parses: int = Field(..., description="失败解析数量")
    results: List[ParseResponse] = Field(..., description="解析结果列表")
    total_duration_ms: int = Field(..., description="总耗时（毫秒）")


class ParseStatusResponse(BaseModel):
    """解析状态响应模式"""
    document_id: str = Field(..., description="文档ID")
    status: str = Field(..., description="解析状态")
    last_parsed_at: Optional[datetime] = Field(None, description="最后解析时间")
    fragment_count: int = Field(..., description="Fragment数量")
    error_message: Optional[str] = Field(None, description="错误信息")


class ParseStatsResponse(BaseModel):
    """解析统计响应模式"""
    kb_id: str = Field(..., description="知识库ID")
    total_documents: int = Field(..., description="总文档数量")
    parsed_documents: int = Field(..., description="已解析文档数量")
    pending_documents: int = Field(..., description="待解析文档数量")
    failed_documents: int = Field(..., description="解析失败文档数量")
    total_fragments: int = Field(..., description="总Fragment数量")
    last_updated: Optional[datetime] = Field(None, description="最后更新时间")