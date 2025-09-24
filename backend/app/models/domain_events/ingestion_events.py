"""
此模块定义了与文档摄入流程相关的领域事件Payload的Pydantic模型。

这些模型作为每种事件类型数据结构的官方“契约”，
在创建和消费事件时确保类型安全和数据验证。
"""
import uuid
import enum
from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

# --- 通用子模型 ---

class FileInfo(BaseModel):
    """描述一个用于处理的文件的基本信息。"""
    filename: str
    size_bytes: int

class ToolExecutionRecord(BaseModel):
    """记录一个外部工具（如CLI程序）的执行详情，用于溯源。"""
    command_executed: str
    start_time: datetime
    end_time: datetime
    input_files: List[FileInfo]
    
    # 新增字段：用于记录工具执行的关键结果摘要
    exit_code: int = Field(description="工具执行的退出码 (0通常代表成功)")
    result: Dict[str, Any] = Field(default_factory=dict, description="包含关键结果指标的字典")


# --- Ingestion Strategy Enums ---

class ContentExtractionStrategy(str, enum.Enum):
    """
    定义在处理文档时如何对待其范式化内容（Canonical Content）的提取策略。
    """
    REUSE_ANY = "reuse_any"
    """
    最高效的策略。如果一个完全相同的范式化内容（基于哈希）已经在系统中被任何文档
    处理过（即已经完成了LibreOffice转换和MinerU提取），则直接复用那次的处理结果
    （包括提取的资产关联和结构化数据），并立即触发“文档已提取”事件，跳过整个
    DOCUMENT_PROCESSING作业。
    """
    FORCE_REEXTRACTION = "force_reextraction"
    """
    最彻底的策略。忽略所有已存在的提取结果，强制为该文档重新执行完整的内容提取流程
    （LibreOffice -> MinerU）。适用于MinerU或LibreOffice版本更新，或提取逻辑
    本身发生重大变化的场景。
    """

class AssetAnalysisStrategy(str, enum.Enum):
    """
    定义在处理文档时如何对待其内嵌资产的分析策略。
    """
    REUSE_ANY = "reuse_any"
    """
    最高效的策略。如果一个完全相同的资产（基于哈希）已经在系统的任何地方被分析过，
    就直接复用那次分析结果，无需重新执行VLM分析。
    """
    REUSE_WITHIN_DOCUMENT = "reuse_within_document"
    """
    一个折中的策略。仅当该资产的上一个分析结果是针对当前这个完全相同的文档时，
    才进行复用。这在需要对文档进行重新处理（例如，使用了新的Chunking或Embedding模型），
    但VLM模型和资产本身没有变化时非常有用。
    """
    FORCE_REANALYSIS = "force_reanalysis"
    """
    最彻底的策略。忽略所有已存在的分析结果，强制为该文档的每一个资产都重新执行
    VLM分析。适用于VLM模型更新或分析逻辑变更的场景。
    """

# --- 事件Payload定义 ---

class DocumentRegisteredPayload(BaseModel):
    """
    当一个新文档被成功上传并创建了初始数据库记录后触发。
    此事件是整个文档处理流水线的起点，并携带了处理指令与策略。
    """
    # 1. 核心标识符
    document_id: uuid.UUID = Field(description="新创建的文档记录的唯一ID")
    knowledge_space_id: uuid.UUID = Field(description="该文档所属的知识空间ID")
    original_id: uuid.UUID = Field(description="关联的原始文件记录的ID")

    # 2. 上传者信息
    initiator_id: uuid.UUID = Field(description="发起本次上传操作的用户的ID")

    # 3. 原始文件元数据
    original_filename: str = Field(description="用户上传时的原始文件名")
    reported_mime_type: str = Field(description="上传时浏览器或客户端报告的MIME类型")
    file_size_bytes: int = Field(description="原始文件的字节大小")

    # 4. 处理指令与策略
    force: bool = Field(default=False, description="是否需要强制处理。如果为True，应覆盖或取消任何已存在的旧作业")
    
    content_extraction_strategy: Optional[ContentExtractionStrategy] = Field(
        default=None,
        description="内容提取策略。如果为None，则使用知识空间或系统的默认策略。"
    )

    asset_analysis_strategy: Optional[AssetAnalysisStrategy] = Field(
        default=None, 
        description="资产分析策略。如果为None，则使用知识空间或系统的默认策略。"
    )
    
    chunking_strategy_name: Optional[str] = Field(
        default=None, 
        description="指定要使用的Chunking策略的名称。如果为None，则使用默认策略。"
    )

class AnalysisTraceabilityInfo(BaseModel):
    """记录资产分析过程中的溯源信息。"""
    model_credential_id: Optional[uuid.UUID]
    model_name: str
    prompt_used: str
    start_time: datetime
    end_time: datetime

class AssetAnalysisCompletedPayload(BaseModel):
    """资产分析成功完成事件的Payload。"""
    asset_id: uuid.UUID
    document_id: uuid.UUID  # 上下文信息：此次分析所属的文档

    # 分析结果
    description: str
    tags: List[str] = Field(default_factory=list, description="由模型生成的标签列表")

    # 溯源信息
    trace_info: AnalysisTraceabilityInfo

class DocumentContentExtractedPayload(BaseModel):
    """
    文档内容提取完成事件的Payload。
    此事件标志着原始文档已被处理，其文本内容和内嵌资产已被成功提取并持久化。
    """
    # 1. 核心标识符
    document_id: uuid.UUID
    knowledge_space_id: uuid.UUID
    initiator_id: uuid.UUID = Field(description="发起原始文档上传操作的用户ID")

    # 2. 提取产物 - 资产
    extracted_asset_ids: List[uuid.UUID] = Field(description="本次提取出的所有资产的唯一ID列表")

    # 3. 提取产物 - 范式化内容
    canonical_content_id: uuid.UUID = Field(description="存储范式化Markdown内容的记录ID")

    # 4. 过程溯源 - LibreOffice
    libre_office_record: Optional[ToolExecutionRecord] = Field(description="LibreOffice转换过程的执行记录")

    # 5. 过程溯源 - MinerU
    mineru_record: Optional[ToolExecutionRecord] = Field(description="MinerU内容提取过程的执行记录")

class DocumentChunkingCompletedPayload(BaseModel):
    """
    文档分块完成事件的Payload。
    此事件标志着文档的内容已被成功分割为语义化的块，可用于后续的索引和检索。
    """
    # 1. 核心标识符
    document_id: uuid.UUID = Field(description="已完成分块的文档ID")
    knowledge_space_id: uuid.UUID = Field(description="该文档所属的知识空间ID")
    
    # 2. 分块结果
    total_chunks_created: int = Field(description="本次分块创建的总块数")
    heading_chunks_count: int = Field(description="标题类型块的数量")
    content_chunks_count: int = Field(description="内容类型块的数量")
    
    # 3. 分块策略信息
    chunking_strategy_used: str = Field(description="实际使用的分块策略名称")
    
    # 4. 过程溯源
    job_id: uuid.UUID = Field(description="执行此次分块的作业ID")
    start_time: datetime = Field(description="分块开始时间")
    end_time: datetime = Field(description="分块结束时间")
    
    # 5. 质量指标
    average_chunk_size: float = Field(description="平均块大小（字符数）")
    processing_lines_total: int = Field(description="处理的总行数")
