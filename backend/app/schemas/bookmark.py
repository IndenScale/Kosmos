
import uuid
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator

# --- Base Schema ---
class BookmarkBase(BaseModel):
    name: str = Field(..., description="书签的名称，例如 'data_security_guideline'。")
    knowledge_space_id: uuid.UUID = Field(..., description="所属知识空间的ID。")
    parent_id: Optional[uuid.UUID] = Field(None, description="父书签的ID，用于创建层级结构。")
    visibility: str = Field("private", description="可见性: 'private' 或 'public'。")
    document_id: Optional[uuid.UUID] = Field(None, description="（可选）指向的文档ID。")
    start_line: Optional[int] = Field(None, description="（可选）起始行号。")
    end_line: Optional[int] = Field(None, description="（可选）结束行号。")

# --- Create Schema ---
class BookmarkCreate(BookmarkBase):
    pass

# --- Update Schema ---
class BookmarkUpdate(BaseModel):
    name: Optional[str] = Field(None, description="新的书签名称。")
    parent_id: Optional[uuid.UUID] = Field(None, description="新的父书签ID。")
    visibility: Optional[str] = Field(None, description="新的可见性设置。")

# --- Response Schema ---
class BookmarkRead(BookmarkBase):
    id: uuid.UUID
    owner_id: uuid.UUID

    class Config:
        from_attributes = True # Pydantic v2
