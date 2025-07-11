from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
from app.models.sdtm import (
    SDTMMode, QualityMetrics, ProgressMetrics, 
    DocumentInfo, AbnormalDocument, EditOperation, 
    DocumentAnnotation, SDTMEngineResponse, SDTMStats
)

class SDTMStatsResponse(BaseModel):
    """SDTM统计信息响应"""
    kb_id: str = Field(..., description="知识库ID")
    progress_metrics: ProgressMetrics
    quality_metrics: QualityMetrics
    abnormal_documents: List[AbnormalDocument] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=datetime.now)

class SDTMProcessRequest(BaseModel):
    """SDTM处理请求"""
    mode: SDTMMode = Field(..., description="运行模式")
    batch_size: int = Field(default=10, description="批处理大小")
    max_iterations: int = Field(default=100, description="最大迭代次数")

class SDTMProcessResponse(BaseModel):
    """SDTM处理响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="处理消息")
    operations: List[EditOperation] = Field(default_factory=list, description="编辑操作列表")
    annotations: List[DocumentAnnotation] = Field(default_factory=list, description="文档标注列表")
    reasoning: str = Field(default="", description="推理过程")
    stats: Optional[SDTMStatsResponse] = Field(None, description="更新后的统计信息")

class TagDictionaryOptimizeRequest(BaseModel):
    """标签字典优化请求"""
    mode: SDTMMode = Field(default=SDTMMode.EDIT, description="运行模式")
    batch_size: int = Field(default=10, description="批处理大小")
    auto_apply: bool = Field(default=False, description="是否自动应用编辑操作")
    # 批处理配置
    abnormal_doc_slots: int = Field(default=3, description="异常文档处理槽位")
    normal_doc_slots: int = Field(default=7, description="正常文档处理槽位")
    # 终止条件配置
    max_iterations: int = Field(default=50, description="最大迭代次数")
    abnormal_doc_threshold: float = Field(default=3.0, description="异常文档数量阈值（百分比）")
    enable_early_termination: bool = Field(default=True, description="是否启用提前终止")

class TagDictionaryOptimizeResponse(BaseModel):
    """标签字典优化响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="处理消息")
    operations: List[EditOperation] = Field(default_factory=list, description="编辑操作列表")
    preview_dictionary: Dict[str, Any] = Field(default_factory=dict, description="预览字典")
    stats: Optional[SDTMStatsResponse] = Field(None, description="统计信息")

class DocumentBatchRequest(BaseModel):
    """文档批处理请求"""
    document_ids: List[str] = Field(..., description="文档ID列表")
    mode: SDTMMode = Field(default=SDTMMode.ANNOTATE, description="运行模式")

class DocumentBatchResponse(BaseModel):
    """文档批处理响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="处理消息")
    annotations: List[DocumentAnnotation] = Field(default_factory=list, description="文档标注列表")
    failed_documents: List[str] = Field(default_factory=list, description="失败的文档ID列表") 