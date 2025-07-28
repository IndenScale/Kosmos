# app/schemas/knowledge_base.py

from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

# 导入凭证相关模式
from app.schemas.credential import KBModelConfigsResponse

class KBRoleEnum(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"

class KBCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_public: bool = False
    # 移除了owner_id字段，因为现在从current_user获取

class KBUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = None

class KBMemberResponse(BaseModel):
    user_id: str
    username: str
    email: str
    role: KBRoleEnum
    created_at: datetime

    class Config:
        from_attributes = True

class KBResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    owner_id: str
    tag_dictionary: Dict[str, Any]
    milvus_collection_id: Optional[str] = None
    is_public: bool
    last_tag_dictionary_update_time: Optional[datetime] = None  # 添加这个字段
    created_at: datetime

    class Config:
        from_attributes = True

class KBDetailResponse(KBResponse):
    members: List[KBMemberResponse]
    owner_username: str
    model_configs: Optional[KBModelConfigsResponse] = None  # 添加模型配置信息

class KBMemberAdd(BaseModel):
    user_id: str
    role: KBRoleEnum

class TagDictionaryUpdate(BaseModel):
    tag_dictionary: Dict[str, Any]  # 直接提供标签字典JSON