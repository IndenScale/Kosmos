# app/models/credential.py

import uuid
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base
from app.utils.db_types import JSONEncodedDict


class ModelAccessCredential(Base):
    """模型访问凭证表

    存储用户的AI模型API访问凭证，包括API Key、Base URL等敏感信息。
    一个用户可以拥有多套凭证，并在不同知识库中复用。
    """
    __tablename__ = "model_access_credentials"
    __table_args__ = (
        {'extend_existing': True}
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)  # 用户自定义的凭证名称，如 "我的OpenAI Key 1"
    provider = Column(String(50), nullable=False)  # 服务提供商, e.g., 'openai', 'azure', 'cohere', 'local'
    model_type = Column(String(20), nullable=False)  # 模型类型: embedding, reranker, llm, vlm
    api_key_encrypted = Column(Text, nullable=False)  # 加密后的 API Key
    base_url = Column(String(1024), nullable=True)  # API endpoint URL
    description = Column(Text, nullable=True)  # 用户备注
    is_active = Column(String(10), default="true", nullable=False)  # 是否启用，使用字符串避免布尔类型问题
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # 关系
    user = relationship("User", back_populates="credentials")
    kb_embedding_configs = relationship("KBModelConfig",
                                      foreign_keys="KBModelConfig.embedding_credential_id",
                                      back_populates="embedding_credential")
    kb_reranker_configs = relationship("KBModelConfig",
                                     foreign_keys="KBModelConfig.reranker_credential_id",
                                     back_populates="reranker_credential")
    kb_llm_configs = relationship("KBModelConfig",
                                foreign_keys="KBModelConfig.llm_credential_id",
                                back_populates="llm_credential")
    kb_vlm_configs = relationship("KBModelConfig",
                                foreign_keys="KBModelConfig.vlm_credential_id",
                                back_populates="vlm_credential")


class KBModelConfig(Base):
    """知识库模型配置表

    存储知识库使用的具体模型配置，包括模型名称和对应的凭证引用。
    将模型配置与凭证分离，便于独立管理和复用。
    """
    __tablename__ = "kb_model_configs"
    __table_args__ = (
        UniqueConstraint('kb_id', name='uq_kb_model_config'),
        {'extend_existing': True}
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    kb_id = Column(String, ForeignKey("knowledge_bases.id"), nullable=False, unique=True)

    # Embedding 配置
    embedding_model_name = Column(String(100), default="text-embedding-3-small", nullable=False)
    embedding_credential_id = Column(String, ForeignKey("model_access_credentials.id"), nullable=True)
    embedding_config_params = Column(JSONEncodedDict, default={})  # JSON格式存储embedding模型调用参数

    # Reranker 配置
    reranker_model_name = Column(String(100), nullable=True)
    reranker_credential_id = Column(String, ForeignKey("model_access_credentials.id"), nullable=True)
    reranker_config_params = Column(JSONEncodedDict, default={})  # JSON格式存储reranker模型调用参数

    # LLM 配置 (用于摘要、标签生成等任务)
    llm_model_name = Column(String(100), default="gpt-4-turbo-preview", nullable=False)
    llm_credential_id = Column(String, ForeignKey("model_access_credentials.id"), nullable=True)
    llm_config_params = Column(JSONEncodedDict, default={})  # JSON格式存储LLM模型调用参数

    # VLM 配置 (视觉语言模型，用于图像处理)
    vlm_model_name = Column(String(100), nullable=True)
    vlm_credential_id = Column(String, ForeignKey("model_access_credentials.id"), nullable=True)
    vlm_config_params = Column(JSONEncodedDict, default={})  # JSON格式存储VLM模型调用参数

    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # 关系
    knowledge_base = relationship("KnowledgeBase", back_populates="model_config")
    embedding_credential = relationship("ModelAccessCredential",
                                      foreign_keys=[embedding_credential_id],
                                      back_populates="kb_embedding_configs")
    reranker_credential = relationship("ModelAccessCredential",
                                     foreign_keys=[reranker_credential_id],
                                     back_populates="kb_reranker_configs")
    llm_credential = relationship("ModelAccessCredential",
                                foreign_keys=[llm_credential_id],
                                back_populates="kb_llm_configs")
    vlm_credential = relationship("ModelAccessCredential",
                                foreign_keys=[vlm_credential_id],
                                back_populates="kb_vlm_configs")