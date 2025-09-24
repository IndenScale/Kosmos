"""此模块提供用于创建分块相关领域事件的辅助函数。"""
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from typing import Dict, Any

from backend.app.models.domain_events import DomainEvent
from backend.app.models.domain_events.ingestion_events import DocumentChunkingCompletedPayload
from backend.app.models import Job, Chunk

def create_document_chunking_completed_event(
    db: Session,
    job: Job,
    chunking_result: Dict[str, Any]
):
    """
    根据分块作业的执行结果，创建并保存一个DocumentChunkingCompleted领域事件。

    此函数应在主业务逻辑的数据库事务中被调用，以确保事件的创建
    与业务状态的变更是原子性的。
    """
    document = job.document
    if not document:
        # 如果没有关联的文档，则不创建事件
        return

    try:
        # 统计分块结果
        total_chunks = db.query(Chunk).filter(Chunk.document_id == document.id).count()
        heading_chunks = db.query(Chunk).filter(
            Chunk.document_id == document.id,
            Chunk.type == "heading"
        ).count()
        content_chunks = db.query(Chunk).filter(
            Chunk.document_id == document.id,
            Chunk.type == "content"
        ).count()
        
        # 计算平均块大小
        chunks = db.query(Chunk).filter(Chunk.document_id == document.id).all()
        total_chars = sum(len(chunk.raw_content or "") for chunk in chunks)
        avg_chunk_size = total_chars / total_chunks if total_chunks > 0 else 0
        
        # 获取分块策略
        chunking_strategy = job.context.get("chunking_params", {}).get("splitter", "rule_based")
        
        # 1. 使用Pydantic模型构建Payload，这会进行数据验证
        payload = DocumentChunkingCompletedPayload(
            document_id=document.id,
            knowledge_space_id=document.knowledge_space_id,
            total_chunks_created=total_chunks,
            heading_chunks_count=heading_chunks,
            content_chunks_count=content_chunks,
            chunking_strategy_used=chunking_strategy,
            job_id=job.id,
            start_time=chunking_result.get("start_time", job.created_at),
            end_time=chunking_result.get("end_time", datetime.utcnow()),
            average_chunk_size=avg_chunk_size,
            processing_lines_total=chunking_result.get("total_lines", 0)
        )

        # 2. 将payload序列化为JSON字符串，因为DomainEvent.payload字段类型为Text
        payload_json_str = payload.model_dump_json()
        
        # 3. 创建DomainEvent的SQLAlchemy模型实例
        domain_event = DomainEvent(
            aggregate_id=str(document.id),
            event_type="DocumentChunkingCompletedPayload",
            payload=payload_json_str,  # 使用JSON字符串而不是dict
            correlation_id=job.id  # 使用Job ID作为关联ID，用于追踪
        )

        # 3. 将事件添加到数据库会话中，等待统一提交
        db.add(domain_event)
        print(f"  - 已创建领域事件 'DocumentChunkingCompleted' (待提交) for document {document.id}")

    except Exception as e:
        # 如果Payload构建失败，只记录错误，不应中断主流程
        print(f"  - 错误：创建 'DocumentChunkingCompleted' 领域事件失败: {e}")