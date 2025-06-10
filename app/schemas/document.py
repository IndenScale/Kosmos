from pydantic import BaseModel, computed_field
from datetime import datetime
from typing import Optional

class DocumentBase(BaseModel):
    filename: str
    file_type: str

class DocumentCreate(DocumentBase):
    pass

class DocumentResponse(DocumentBase):
    id: str
    created_at: datetime
    
    # 通过计算字段获取物理文件信息
    @computed_field
    @property
    def file_size(self) -> int:
        return self.physical_file.file_size if hasattr(self, 'physical_file') and self.physical_file else 0
    
    @computed_field
    @property
    def file_path(self) -> str:
        return self.physical_file.file_path if hasattr(self, 'physical_file') and self.physical_file else ""
    
    class Config:
        from_attributes = True

class KBDocumentResponse(BaseModel):
    kb_id: str
    document_id: str
    upload_at: datetime
    last_ingest_time: Optional[datetime] = None  # 添加这个字段
    document: DocumentResponse
    chunk_count: int = 0
    uploader_username: Optional[str] = None
    
    # 通过计算字段获取上传者信息
    @computed_field
    @property
    def uploaded_by(self) -> str:
        return self.document.uploaded_by if hasattr(self.document, 'uploaded_by') else ""
    
    class Config:
        from_attributes = True

class DocumentListResponse(BaseModel):
    documents: list[KBDocumentResponse]
    total: int