from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Union, Any
from datetime import datetime
import enum
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base
import uuid

class SDTMMode(enum.Enum):
    """SDTM运行模式枚举"""
    EDIT = "edit"  # 编辑模式 - 更新字典
    ANNOTATE = "annotate"  # 标注模式 - 标注文档
    SHADOW = "shadow"  # 影子模式 - 监测语义漂移

class QualityMetrics(BaseModel):
    """质量指标模型"""
    tags_document_distribution: Dict[str, int] = Field(default_factory=dict, description="每个文档的标签数量分布")
    documents_tag_distribution: Dict[str, int] = Field(default_factory=dict, description="每个标签的文档数量分布")
    under_annotated_docs_count: int = Field(default=0, description="标注不足的文档数量")
    over_annotated_docs_count: int = Field(default=0, description="标注过度的文档数量")
    under_used_tags_count: int = Field(default=0, description="使用不足的标签数量")
    over_used_tags_count: int = Field(default=0, description="使用过度的标签数量")
    indistinguishable_docs_count: int = Field(default=0, description="无法区分的文档数量")

class ProgressMetrics(BaseModel):
    """进度指标模型"""
    current_iteration: int = Field(default=0, description="当前迭代次数")
    total_iterations: int = Field(default=100, description="总迭代次数")
    current_tags_dictionary_size: int = Field(default=0, description="当前标签字典大小")
    max_tags_dictionary_size: int = Field(default=1000, description="最大标签字典大小")
    progress_pct: float = Field(default=0.0, description="进度百分比")
    capacity_pct: float = Field(default=0.0, description="容量百分比")
    
    def __init__(self, **data):
        # 计算百分比字段
        current_iteration = data.get('current_iteration', 0)
        total_iterations = data.get('total_iterations', 100)
        current_tags_dictionary_size = data.get('current_tags_dictionary_size', 0)
        max_tags_dictionary_size = data.get('max_tags_dictionary_size', 1000)
        
        # 计算进度百分比
        if total_iterations == 0:
            data['progress_pct'] = 0.0
        else:
            data['progress_pct'] = (current_iteration / total_iterations) * 100
        
        # 计算容量百分比
        if max_tags_dictionary_size == 0:
            data['capacity_pct'] = 0.0
        else:
            data['capacity_pct'] = (current_tags_dictionary_size / max_tags_dictionary_size) * 100
        
        super().__init__(**data)

class DocumentInfo(BaseModel):
    """文档信息模型"""
    doc_id: str = Field(..., description="文档ID")
    content: str = Field(..., description="文档内容")
    current_tags: List[str] = Field(default_factory=list, description="当前标签")
    kb_id: str = Field(..., description="知识库ID")
    chunk_index: int = Field(default=0, description="片段索引")

class AbnormalDocument(BaseModel):
    """异常文档模型"""
    doc_id: str = Field(..., description="文档ID")
    reason: str = Field(..., description="异常原因")
    content: str = Field(..., description="文档内容")
    current_tags: List[str] = Field(default_factory=list, description="当前标签")
    anomaly_type: str = Field(..., description="异常类型：under_annotated/over_annotated/indistinguishable")

class EditOperation(BaseModel):
    """编辑操作模型"""
    position: str = Field(..., description="编辑位置，如'数据安全评估.控制域.安全组织与人员'")
    payload: Dict[str, Any] = Field(..., description="编辑内容")

class DocumentAnnotation(BaseModel):
    """文档标注模型"""
    doc_id: str = Field(..., description="文档ID")
    tags: List[str] = Field(..., description="标签列表")
    confidence: float = Field(..., description="置信度")

class SDTMEngineResponse(BaseModel):
    """SDTM引擎响应模型"""
    operations: List[EditOperation] = Field(default_factory=list, description="编辑操作列表")
    annotations: List[DocumentAnnotation] = Field(default_factory=list, description="文档标注列表")
    reasoning: str = Field(default="", description="推理过程")
    updated_dictionary: Optional[Dict[str, Any]] = Field(default=None, description="更新后的标签字典")

class SDTMStats(BaseModel):
    """SDTM统计信息模型"""
    progress_metrics: ProgressMetrics
    quality_metrics: QualityMetrics
    abnormal_documents: List[AbnormalDocument] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=datetime.now)

class SDTMProcessRequest(BaseModel):
    """SDTM处理请求模型"""
    mode: SDTMMode = Field(..., description="运行模式")
    batch_size: int = Field(default=10, description="批处理大小")
    max_iterations: int = Field(default=100, description="最大迭代次数")

class SDTMJob(Base):
    """SDTM任务表"""
    __tablename__ = "sdtm_jobs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    kb_id = Column(String, ForeignKey("knowledge_bases.id"), nullable=False)
    mode = Column(String, nullable=False)  # edit, annotate, shadow
    batch_size = Column(Integer, default=10)
    auto_apply = Column(Boolean, default=True)
    status = Column(String, default="pending")  # pending, processing, completed, failed
    task_id = Column(String, nullable=True)  # 任务队列中的task_id
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    error_message = Column(Text, nullable=True)
    result = Column(Text, nullable=True)  # JSON格式的结果
    
    # 关系
    knowledge_base = relationship("KnowledgeBase") 