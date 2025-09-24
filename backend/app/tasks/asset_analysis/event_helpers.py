"""
此模块提供用于创建资产分析相关领域事件的辅助函数。
"""
import uuid
from sqlalchemy.orm import Session
from typing import Dict, Any

from backend.app.models.domain_events import DomainEvent
from backend.app.models.domain_events.ingestion_events import AssetAnalysisCompletedPayload

def create_asset_analysis_completed_event(
    db: Session,
    payload: AssetAnalysisCompletedPayload,
    correlation_id: uuid.UUID
):
    """
    创建一个AssetAnalysisCompleted领域事件并将其添加到数据库会话中。
    """
    try:
        # Serialize payload to JSON string to match DomainEvent.payload field type (Text)
        payload_json_str = payload.model_dump_json(exclude_none=True)
        
        domain_event = DomainEvent(
            aggregate_id=str(payload.asset_id),
            event_type="AssetAnalysisCompletedPayload",
            payload=payload_json_str,
            correlation_id=correlation_id
        )
        db.add(domain_event)
        print(f"  - 已创建领域事件 'AssetAnalysisCompleted' (待提交) for asset {payload.asset_id}")
    except Exception as e:
        print(f"  - 错误：创建 'AssetAnalysisCompleted' 领域事件失败: {e}")
