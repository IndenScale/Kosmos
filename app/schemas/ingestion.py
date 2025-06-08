from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class IngestionJobResponse(BaseModel):
    id: str
    kb_id: str
    document_id: str
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class IngestionJobListResponse(BaseModel):
    jobs: List[IngestionJobResponse]
    total: int

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