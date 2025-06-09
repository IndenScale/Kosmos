from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class DocumentBase(BaseModel):
    filename: str
    file_type: str
    file_size: int

class DocumentCreate(DocumentBase):
    pass

class DocumentResponse(DocumentBase):
    id: str
    file_path: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class KBDocumentResponse(BaseModel):
    kb_id: str
    document_id: str
    uploaded_by: str
    upload_at: datetime
    document: DocumentResponse
    chunk_count: int = 0
    uploader_username: Optional[str] = None  # 新增用户名字段
    
    class Config:
        from_attributes = True

class DocumentListResponse(BaseModel):
    documents: list[KBDocumentResponse]
    total: int