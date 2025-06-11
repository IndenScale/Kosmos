from pydantic import BaseModel, computed_field
from datetime import datetime
from typing import Optional, List, Dict

class DocumentBase(BaseModel):
    filename: str
    file_type: str

class DocumentCreate(DocumentBase):
    pass

class DocumentResponse(DocumentBase):
    id: str
    created_at: datetime
    file_size: int = 0  # 直接作为字段，不使用computed_field
    file_path: str = ""  # 直接作为字段，不使用computed_field

    class Config:
        from_attributes = True

class KBDocumentResponse(BaseModel):
    kb_id: str
    document_id: str
    upload_at: datetime
    last_ingest_time: Optional[datetime] = None
    document: DocumentResponse
    chunk_count: int = 0
    uploader_username: Optional[str] = None
    is_index_outdated: bool = False  # 新增：索引是否失效

    class Config:
        from_attributes = True

class DocumentListResponse(BaseModel):
    documents: list[KBDocumentResponse]
    total: int

# 添加批量删除请求模型
class BatchDeleteRequest(BaseModel):
    document_ids: List[str]

# 添加批量删除响应模型
class BatchDeleteResponse(BaseModel):
    results: Dict[str, bool]
    success_count: int
    failed_count: int