"""
模型访问凭证相关的Pydantic模式
文件: credential.py
创建时间: 2025-07-26
描述: 定义凭证管理的请求和响应模式
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator, computed_field
from datetime import datetime
from enum import Enum


class ModelType(str, Enum):
    """模型类型枚举"""
    EMBEDDING = "embedding"
    RERANKER = "reranker"
    LLM = "llm"
    VLM = "vlm"


class CredentialBase(BaseModel):
    """凭证基础模式"""
    name: str = Field(..., description="凭证名称")
    provider: str = Field(..., description="服务提供商")
    model_type: ModelType = Field(..., description="模型类型")
    base_url: str = Field(..., description="API基础URL")
    description: Optional[str] = Field(None, description="凭证描述")


class CredentialCreate(CredentialBase):
    """创建凭证请求模式"""
    api_key: str = Field(..., description="API密钥")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError('凭证名称不能为空')
        return v.strip()

    @field_validator('provider')
    @classmethod
    def validate_provider(cls, v):
        if not v or not v.strip():
            raise ValueError('服务提供商不能为空')
        return v.strip()

    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v):
        if not v or not v.strip():
            raise ValueError('API密钥不能为空')
        return v.strip()

    @field_validator('base_url')
    @classmethod
    def validate_base_url(cls, v):
        if not v or not v.strip():
            raise ValueError('Base URL不能为空')
        v = v.strip()
        if not v.startswith(('http://', 'https://')):
            raise ValueError('Base URL必须以http://或https://开头')
        return v.rstrip('/')


class CredentialUpdate(BaseModel):
    """更新凭证请求模式"""
    name: Optional[str] = Field(None, description="凭证名称")
    provider: Optional[str] = Field(None, description="服务提供商")
    api_key: Optional[str] = Field(None, description="API密钥")
    base_url: Optional[str] = Field(None, description="API基础URL")
    description: Optional[str] = Field(None, description="凭证描述")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        if v is not None and (not v or not v.strip()):
            raise ValueError('凭证名称不能为空')
        return v.strip() if v else v

    @field_validator('provider')
    @classmethod
    def validate_provider(cls, v):
        if v is not None and (not v or not v.strip()):
            raise ValueError('服务提供商不能为空')
        return v.strip() if v else v

    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v):
        if v is not None and (not v or not v.strip()):
            raise ValueError('API密钥不能为空')
        return v.strip() if v else v

    @field_validator('base_url')
    @classmethod
    def validate_base_url(cls, v):
        if v is not None:
            if not v or not v.strip():
                raise ValueError('Base URL不能为空')
            v = v.strip()
            if not v.startswith(('http://', 'https://')):
                raise ValueError('Base URL必须以http://或https://开头')
            return v.rstrip('/')
        return v


class CredentialResponse(BaseModel):
    """凭证响应模式"""
    id: str = Field(..., description="凭证ID")
    user_id: str = Field(..., description="用户ID")
    name: str = Field(..., description="凭证名称")
    provider: str = Field(..., description="服务提供商")
    model_type: ModelType = Field(..., description="模型类型")
    base_url: str = Field(..., description="API基础URL")
    description: Optional[str] = Field(None, description="凭证描述")
    api_key_encrypted: str = Field(..., description="加密后的API密钥")
    is_active: str = Field(..., description="是否启用")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    api_key_display: str = Field("", description="掩码后的API密钥")

    model_config = {"from_attributes": True}


class KBModelConfigCreate(BaseModel):
    """创建知识库模型配置请求模式"""
    kb_id: str = Field(..., description="知识库ID")
    credential_id: str = Field(..., description="凭证ID")
    model_name: str = Field(..., description="模型名称")
    config_params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="配置参数")

    @field_validator('model_name')
    @classmethod
    def validate_model_name(cls, v):
        if not v or not v.strip():
            raise ValueError('模型名称不能为空')
        return v.strip()


class KBModelConfigUpdate(BaseModel):
    """更新知识库模型配置请求模式"""
    credential_id: str = Field(..., description="凭证ID")
    model_name: Optional[str] = Field(None, description="模型名称")
    config_params: Optional[Dict[str, Any]] = Field(None, description="配置参数")

    @field_validator('model_name')
    @classmethod
    def validate_model_name(cls, v):
        if v is not None and (not v or not v.strip()):
            raise ValueError('模型名称不能为空')
        return v.strip() if v else v


class KBModelConfigResponse(BaseModel):
    """知识库模型配置响应模式"""
    id: str = Field(..., description="配置ID")
    kb_id: str = Field(..., description="知识库ID")
    model_name: str = Field(..., description="模型名称")
    credential_id: str = Field(..., description="凭证ID")
    config_params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="配置参数")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    # 关联的凭证信息（不包含敏感信息）
    credential: Optional[CredentialResponse] = Field(None, description="关联的凭证信息")

    model_config = {"from_attributes": True}


class KBModelConfigsResponse(BaseModel):
    """知识库所有模型配置响应模式"""
    kb_id: str = Field(..., description="知识库ID")
    configs: List[KBModelConfigResponse] = Field(..., description="模型配置列表")


class CredentialListResponse(BaseModel):
    """凭证列表响应模式"""
    credentials: List[CredentialResponse] = Field(..., description="凭证列表")
    total: int = Field(..., description="总数量")


class ModelTypeInfo(BaseModel):
    """模型类型信息"""
    type: ModelType = Field(..., description="模型类型")
    name: str = Field(..., description="类型名称")
    description: str = Field(..., description="类型描述")


class ModelTypesResponse(BaseModel):
    """支持的模型类型响应"""
    model_types: List[ModelTypeInfo] = Field(..., description="支持的模型类型列表")

    @classmethod
    def get_default(cls):
        """获取默认的模型类型信息"""
        type_info = {
            ModelType.EMBEDDING: {
                "name": "Embedding模型",
                "description": "用于文档向量化和语义搜索的嵌入模型"
            },
            ModelType.RERANKER: {
                "name": "Reranker模型",
                "description": "用于搜索结果重排序的模型"
            },
            ModelType.LLM: {
                "name": "大语言模型",
                "description": "用于文本生成和对话的大语言模型"
            },
            ModelType.VLM: {
                "name": "视觉语言模型",
                "description": "用于图像理解和多模态处理的视觉语言模型"
            }
        }

        model_types = []
        for model_type in ModelType:
            info = type_info.get(model_type, {"name": model_type.value, "description": ""})
            model_types.append(ModelTypeInfo(
                type=model_type,
                name=info["name"],
                description=info["description"]
            ))

        return cls(model_types=model_types)