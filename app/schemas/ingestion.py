from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class IngestionJobResponse(BaseModel):
    id: str
    kb_id: str
    document_id: str
    task_id: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# 添加新的摄取启动响应模型
class IngestionStartResponse(BaseModel):
    """摄取任务启动响应"""
    id: str
    status: str
    message: str
    success: bool = True

class IngestionJobListResponse(BaseModel):
    jobs: List[IngestionJobResponse]
    total: int

class QueueStatsResponse(BaseModel):
    pending: int = 0
    running: int = 0
    total_tasks: int = 0
    completed: Optional[int] = 0
    failed: Optional[int] = 0
    timeout: Optional[int] = 0

class ChunkResponse(BaseModel):
    id: str
    kb_id: str
    document_id: str
    chunk_index: int
    content: str
    tags: List[str]
    created_at: datetime

    class Config:
        from_attributes = True