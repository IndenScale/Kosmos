"""
模型访问凭证服务
文件: credential_service.py
创建时间: 2025-07-26
描述: 管理用户的模型访问凭证（MAC）
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_
from cryptography.fernet import Fernet
import os
import base64
from datetime import datetime

from app.models.credential import ModelAccessCredential, KBModelConfig
from app.models.knowledge_base import KnowledgeBase
from app.schemas.credential import (
    ModelType, CredentialCreate, CredentialUpdate, CredentialResponse,
    KBModelConfigCreate, KBModelConfigUpdate, KBModelConfigResponse
)


class CredentialService:
    """模型访问凭证服务"""

    def __init__(self):
        # 从环境变量获取加密密钥，如果没有则生成一个
        encryption_key = os.getenv('CREDENTIAL_ENCRYPTION_KEY')
        if not encryption_key:
            # 生成新密钥（生产环境中应该预先设置）
            encryption_key = Fernet.generate_key().decode()
            print(f"警告: 未设置CREDENTIAL_ENCRYPTION_KEY，使用临时密钥: {encryption_key}")

        if isinstance(encryption_key, str):
            encryption_key = encryption_key.encode()

        self.cipher = Fernet(encryption_key)

    def _encrypt_api_key(self, api_key: str) -> str:
        """加密API Key"""
        if not api_key:
            return ""
        return self.cipher.encrypt(api_key.encode()).decode()

    def _decrypt_api_key(self, encrypted_api_key: str) -> str:
        """解密API Key"""
        if not encrypted_api_key:
            return ""
        return self.cipher.decrypt(encrypted_api_key.encode()).decode()

    def create_credential(
        self,
        db: Session,
        user_id: str,
        credential_data: CredentialCreate
    ) -> ModelAccessCredential:
        """创建新的模型访问凭证"""

        # 加密API Key
        encrypted_api_key = self._encrypt_api_key(credential_data.api_key)

        credential = ModelAccessCredential(
            user_id=user_id,
            name=credential_data.name,
            provider=credential_data.provider,
            model_type=credential_data.model_type.value,  # 转换为字符串
            api_key_encrypted=encrypted_api_key,
            base_url=credential_data.base_url,
            description=credential_data.description
        )

        db.add(credential)
        db.commit()
        db.refresh(credential)

        return credential

    def get_user_credentials(
        self,
        db: Session,
        user_id: str,
        model_type: Optional[ModelType] = None
    ) -> List[ModelAccessCredential]:
        """获取用户的所有凭证"""
        query = db.query(ModelAccessCredential).filter(
            ModelAccessCredential.user_id == user_id
        )

        if model_type:
            query = query.filter(ModelAccessCredential.model_type == model_type.value)

        return query.order_by(ModelAccessCredential.created_at.desc()).all()

    def get_credential_by_id(
        self,
        db: Session,
        credential_id: str,
        user_id: str
    ) -> Optional[ModelAccessCredential]:
        """根据ID获取凭证（仅限用户自己的凭证）"""
        return db.query(ModelAccessCredential).filter(
            and_(
                ModelAccessCredential.id == credential_id,
                ModelAccessCredential.user_id == user_id
            )
        ).first()

    def update_credential(
        self,
        db: Session,
        credential_id: str,
        user_id: str,
        credential_data: CredentialUpdate
    ) -> Optional[ModelAccessCredential]:
        """更新凭证"""
        credential = self.get_credential_by_id(db, credential_id, user_id)
        if not credential:
            return None

        # 更新字段
        if credential_data.name is not None:
            credential.name = credential_data.name

        if credential_data.provider is not None:
            credential.provider = credential_data.provider

        if credential_data.api_key is not None:
            credential.api_key_encrypted = self._encrypt_api_key(credential_data.api_key)

        if credential_data.base_url is not None:
            credential.base_url = credential_data.base_url

        if credential_data.description is not None:
            credential.description = credential_data.description

        credential.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(credential)

        return credential

    def delete_credential(
        self,
        db: Session,
        credential_id: str,
        user_id: str
    ) -> bool:
        """删除凭证"""
        credential = self.get_credential_by_id(db, credential_id, user_id)
        if not credential:
            return False

        # 检查是否有知识库在使用此凭证
        # KBModelConfig 有四个不同的凭证字段，需要分别检查
        from sqlalchemy import or_
        kb_configs = db.query(KBModelConfig).filter(
            or_(
                KBModelConfig.embedding_credential_id == credential_id,
                KBModelConfig.reranker_credential_id == credential_id,
                KBModelConfig.llm_credential_id == credential_id,
                KBModelConfig.vlm_credential_id == credential_id
            )
        ).all()

        if kb_configs:
            kb_names = [config.knowledge_base.name for config in kb_configs]
            raise ValueError(f"无法删除凭证，以下知识库正在使用: {', '.join(kb_names)}")

        db.delete(credential)
        db.commit()

        return True

    def get_decrypted_api_key(
        self,
        db: Session,
        credential_id: str,
        user_id: str
    ) -> Optional[str]:
        """获取解密后的API Key（仅用于内部服务调用）"""
        credential = self.get_credential_by_id(db, credential_id, user_id)
        if not credential:
            return None

        return self._decrypt_api_key(credential.api_key_encrypted)

    def get_api_key_display(self, encrypted_api_key: str) -> str:
        """根据解密后的API Key生成用于显示的掩码版本"""
        if not encrypted_api_key:
            return ""

        try:
            decrypted_key = self._decrypt_api_key(encrypted_api_key)
        except Exception:
            # 如果解密失败，返回一个通用的掩码
            return "****...****"

        if not decrypted_key:
            return ""

        # 根据密钥格式应用不同的掩码规则
        if decrypted_key.startswith("sk-") and len(decrypted_key) > 7:
            # OpenAI-like: sk-xxx...xxx
            return f"{decrypted_key[:5]}...{decrypted_key[-3:]}"
        elif len(decrypted_key) > 8:
            # Generic: xxxx...xxxx
            return f"{decrypted_key[:4]}...{decrypted_key[-4:]}"
        else:
            # Too short to mask
            return decrypted_key

    def create_kb_model_config(
        self,
        db: Session,
        user_id: str,
        config_data: KBModelConfigCreate
    ) -> KBModelConfig:
        """为知识库创建模型配置"""

        # 验证知识库所有权
        kb = db.query(KnowledgeBase).filter(
            and_(
                KnowledgeBase.id == config_data.kb_id,
                KnowledgeBase.owner_id == user_id
            )
        ).first()

        if not kb:
            raise ValueError("知识库不存在或无权限")

        # 验证凭证所有权并获取凭证类型
        credential = self.get_credential_by_id(db, config_data.credential_id, user_id)
        if not credential:
            raise ValueError("凭证不存在或无权限")

        # 检查知识库是否已存在配置
        existing_config = db.query(KBModelConfig).filter(
            KBModelConfig.kb_id == config_data.kb_id
        ).first()

        if existing_config:
            # 检查是否已经配置了相同类型的模型
            model_type = credential.model_type
            existing_model_configured = False

            if model_type == ModelType.EMBEDDING.value and existing_config.embedding_credential_id:
                existing_model_configured = True
            elif model_type == ModelType.RERANKER.value and existing_config.reranker_credential_id:
                existing_model_configured = True
            elif model_type == ModelType.LLM.value and existing_config.llm_credential_id:
                existing_model_configured = True
            elif model_type == ModelType.VLM.value and existing_config.vlm_credential_id:
                existing_model_configured = True

            if existing_model_configured:
                raise ValueError(f"知识库已存在 {model_type} 类型的模型配置，请使用 PUT /api/v1/credentials/kb-configs/{existing_config.id} 接口进行更新")

        # 创建新的配置记录或使用现有记录
        if not existing_config:
            config = KBModelConfig(kb_id=config_data.kb_id)
            db.add(config)
        else:
            config = existing_config

        # 根据凭证的模型类型智能设置对应的字段
        if credential.model_type == ModelType.EMBEDDING.value:
            config.embedding_model_name = config_data.model_name
            config.embedding_credential_id = config_data.credential_id
            config.embedding_config_params = config_data.config_params or {}
        elif credential.model_type == ModelType.RERANKER.value:
            config.reranker_model_name = config_data.model_name
            config.reranker_credential_id = config_data.credential_id
            config.reranker_config_params = config_data.config_params or {}
        elif credential.model_type == ModelType.LLM.value:
            config.llm_model_name = config_data.model_name
            config.llm_credential_id = config_data.credential_id
            config.llm_config_params = config_data.config_params or {}
        elif credential.model_type == ModelType.VLM.value:
            config.vlm_model_name = config_data.model_name
            config.vlm_credential_id = config_data.credential_id
            config.vlm_config_params = config_data.config_params or {}
        else:
            raise ValueError(f"不支持的模型类型: {credential.model_type}")

        config.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(config)

        return config

    def get_kb_model_configs(
        self,
        db: Session,
        kb_id: str,
        user_id: str
    ) -> List[KBModelConfig]:
        """获取知识库的所有模型配置"""

        # 验证知识库访问权限（所有者或成员）
        kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
        if not kb:
            raise ValueError("知识库不存在")

        # 这里可以添加更复杂的权限检查逻辑
        # 暂时只检查所有者权限
        if kb.owner_id != user_id:
            raise ValueError("无权限访问此知识库")

        return db.query(KBModelConfig).filter(
            KBModelConfig.kb_id == kb_id
        ).all()

    def _parse_composite_config_id(self, composite_id: str) -> tuple[str, Optional[str]]:
        """解析复合配置ID，返回 (真实ID, 模型类型)"""
        if '_' in composite_id:
            parts = composite_id.rsplit('_', 1)
            if len(parts) == 2 and parts[1] in ['embedding', 'reranker', 'llm', 'vlm']:
                return parts[0], parts[1]
        return composite_id, None

    def update_kb_model_config(
        self,
        db: Session,
        config_id: str,
        user_id: str,
        config_data: KBModelConfigUpdate
    ) -> Optional[KBModelConfig]:
        """更新知识库模型配置"""

        # 解析复合ID
        real_config_id, target_model_type = self._parse_composite_config_id(config_id)

        config = db.query(KBModelConfig).filter(
            KBModelConfig.id == real_config_id
        ).first()

        if not config:
            return None

        # 验证知识库所有权
        if config.knowledge_base.owner_id != user_id:
            raise ValueError("无权限修改此配置")

        # 验证凭证所有权并获取凭证类型
        credential = self.get_credential_by_id(db, config_data.credential_id, user_id)
        if not credential:
            raise ValueError("凭证不存在或无权限")

        # 如果指定了目标模型类型，验证凭证类型是否匹配
        if target_model_type:
            expected_type = target_model_type
            if credential.model_type != expected_type:
                raise ValueError(f"凭证类型 {credential.model_type} 与目标配置类型 {expected_type} 不匹配")

        # 根据凭证的模型类型智能更新对应的字段
        if credential.model_type == ModelType.EMBEDDING.value:
            if config_data.model_name is not None:
                config.embedding_model_name = config_data.model_name
            config.embedding_credential_id = config_data.credential_id
            if config_data.config_params is not None:
                config.embedding_config_params = config_data.config_params
        elif credential.model_type == ModelType.RERANKER.value:
            if config_data.model_name is not None:
                config.reranker_model_name = config_data.model_name
            config.reranker_credential_id = config_data.credential_id
            if config_data.config_params is not None:
                config.reranker_config_params = config_data.config_params
        elif credential.model_type == ModelType.LLM.value:
            if config_data.model_name is not None:
                config.llm_model_name = config_data.model_name
            config.llm_credential_id = config_data.credential_id
            if config_data.config_params is not None:
                config.llm_config_params = config_data.config_params
        elif credential.model_type == ModelType.VLM.value:
            if config_data.model_name is not None:
                config.vlm_model_name = config_data.model_name
            config.vlm_credential_id = config_data.credential_id
            if config_data.config_params is not None:
                config.vlm_config_params = config_data.config_params
        else:
            raise ValueError(f"不支持的模型类型: {credential.model_type}")

        config.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(config)

        return config

    def get_kb_model_config_response(
        self,
        db: Session,
        config: KBModelConfig,
        user_id: str,
        preferred_model_type: Optional[str] = None
    ) -> "KBModelConfigResponse":
        """将KBModelConfig转换为响应格式"""
        from app.schemas.credential import CredentialResponse, KBModelConfigResponse

        # 收集所有可用的模型配置
        available_configs = []

        if config.embedding_model_name and config.embedding_credential_id:
            available_configs.append({
                'type': ModelType.EMBEDDING.value,
                'model_name': config.embedding_model_name,
                'credential_id': config.embedding_credential_id,
                'config_params': config.embedding_config_params or {}
            })

        if config.reranker_model_name and config.reranker_credential_id:
            available_configs.append({
                'type': ModelType.RERANKER.value,
                'model_name': config.reranker_model_name,
                'credential_id': config.reranker_credential_id,
                'config_params': config.reranker_config_params or {}
            })

        if config.llm_model_name and config.llm_credential_id:
            available_configs.append({
                'type': ModelType.LLM.value,
                'model_name': config.llm_model_name,
                'credential_id': config.llm_credential_id,
                'config_params': config.llm_config_params or {}
            })

        if config.vlm_model_name and config.vlm_credential_id:
            available_configs.append({
                'type': ModelType.VLM.value,
                'model_name': config.vlm_model_name,
                'credential_id': config.vlm_credential_id,
                'config_params': config.vlm_config_params or {}
            })

        # 选择要返回的配置
        selected_config = None

        # 如果指定了首选模型类型，优先返回该类型
        if preferred_model_type:
            for cfg in available_configs:
                if cfg['type'] == preferred_model_type:
                    selected_config = cfg
                    break

        # 如果没有指定首选类型或找不到首选类型，返回第一个可用配置
        if not selected_config and available_configs:
            selected_config = available_configs[0]

        # 如果没有任何配置，返回空值
        if not selected_config:
            return KBModelConfigResponse(
                id=config.id,
                kb_id=config.kb_id,
                model_name=None,
                credential_id=None,
                config_params={},
                created_at=config.created_at,
                updated_at=config.updated_at,
                credential=None
            )

        # 获取关联的凭证信息
        credential = None
        credential_response = None
        if selected_config['credential_id']:
            credential = self.get_credential_by_id(db, selected_config['credential_id'], user_id)
            if credential:
                credential_response = CredentialResponse(
                    id=credential.id,
                    user_id=credential.user_id,
                    name=credential.name,
                    provider=credential.provider,
                    model_type=credential.model_type,
                    api_key_encrypted=credential.api_key_encrypted,
                    base_url=credential.base_url,
                    description=credential.description,
                    is_active=credential.is_active,
                    created_at=credential.created_at,
                    updated_at=credential.updated_at
                )

        return KBModelConfigResponse(
            id=config.id,
            kb_id=config.kb_id,
            model_name=selected_config['model_name'],
            credential_id=selected_config['credential_id'],
            config_params=selected_config['config_params'],
            created_at=config.created_at,
            updated_at=config.updated_at,
            credential=credential_response
        )

    def get_kb_model_configs_response(
        self,
        db: Session,
        kb_id: str,
        user_id: str
    ) -> "KBModelConfigsResponse":
        """获取知识库的所有模型配置并转换为响应格式"""
        from app.schemas.credential import KBModelConfigsResponse, KBModelConfigResponse, CredentialResponse

        configs = self.get_kb_model_configs(db, kb_id, user_id)

        config_responses = []

        for config in configs:
            # 为每种非空的模型类型创建一个单独的响应

            # Embedding 配置
            if config.embedding_model_name and config.embedding_credential_id:
                credential = self.get_credential_by_id(db, config.embedding_credential_id, user_id)
                credential_response = None
                if credential:
                    credential_response = CredentialResponse(
                        id=credential.id,
                        user_id=credential.user_id,
                        name=credential.name,
                        provider=credential.provider,
                        model_type=credential.model_type,
                        api_key_encrypted=credential.api_key_encrypted,
                        base_url=credential.base_url,
                        description=credential.description,
                        is_active=credential.is_active,
                        created_at=credential.created_at,
                        updated_at=credential.updated_at
                    )

                config_responses.append(KBModelConfigResponse(
                    id=f"{config.id}_embedding",  # 使用复合ID区分不同类型
                    kb_id=config.kb_id,
                    model_name=config.embedding_model_name,
                    credential_id=config.embedding_credential_id,
                    config_params=config.embedding_config_params or {},
                    created_at=config.created_at,
                    updated_at=config.updated_at,
                    credential=credential_response
                ))

            # Reranker 配置
            if config.reranker_model_name and config.reranker_credential_id:
                credential = self.get_credential_by_id(db, config.reranker_credential_id, user_id)
                credential_response = None
                if credential:
                    credential_response = CredentialResponse(
                        id=credential.id,
                        user_id=credential.user_id,
                        name=credential.name,
                        provider=credential.provider,
                        model_type=credential.model_type,
                        api_key_encrypted=credential.api_key_encrypted,
                        base_url=credential.base_url,
                        description=credential.description,
                        is_active=credential.is_active,
                        created_at=credential.created_at,
                        updated_at=credential.updated_at
                    )

                config_responses.append(KBModelConfigResponse(
                    id=f"{config.id}_reranker",
                    kb_id=config.kb_id,
                    model_name=config.reranker_model_name,
                    credential_id=config.reranker_credential_id,
                    config_params=config.reranker_config_params or {},
                    created_at=config.created_at,
                    updated_at=config.updated_at,
                    credential=credential_response
                ))

            # LLM 配置
            if config.llm_model_name and config.llm_credential_id:
                credential = self.get_credential_by_id(db, config.llm_credential_id, user_id)
                credential_response = None
                if credential:
                    credential_response = CredentialResponse(
                        id=credential.id,
                        user_id=credential.user_id,
                        name=credential.name,
                        provider=credential.provider,
                        model_type=credential.model_type,
                        api_key_encrypted=credential.api_key_encrypted,
                        base_url=credential.base_url,
                        description=credential.description,
                        is_active=credential.is_active,
                        created_at=credential.created_at,
                        updated_at=credential.updated_at
                    )

                config_responses.append(KBModelConfigResponse(
                    id=f"{config.id}_llm",
                    kb_id=config.kb_id,
                    model_name=config.llm_model_name,
                    credential_id=config.llm_credential_id,
                    config_params=config.llm_config_params or {},
                    created_at=config.created_at,
                    updated_at=config.updated_at,
                    credential=credential_response
                ))

            # VLM 配置
            if config.vlm_model_name and config.vlm_credential_id:
                credential = self.get_credential_by_id(db, config.vlm_credential_id, user_id)
                credential_response = None
                if credential:
                    credential_response = CredentialResponse(
                        id=credential.id,
                        user_id=credential.user_id,
                        name=credential.name,
                        provider=credential.provider,
                        model_type=credential.model_type,
                        api_key_encrypted=credential.api_key_encrypted,
                        base_url=credential.base_url,
                        description=credential.description,
                        is_active=credential.is_active,
                        created_at=credential.created_at,
                        updated_at=credential.updated_at
                    )

                config_responses.append(KBModelConfigResponse(
                    id=f"{config.id}_vlm",
                    kb_id=config.kb_id,
                    model_name=config.vlm_model_name,
                    credential_id=config.vlm_credential_id,
                    config_params=config.vlm_config_params or {},
                    created_at=config.created_at,
                    updated_at=config.updated_at,
                    credential=credential_response
                ))

        return KBModelConfigsResponse(
            kb_id=kb_id,
            configs=config_responses
        )

    def delete_kb_model_config(
        self,
        db: Session,
        config_id: str,
        user_id: str
    ) -> bool:
        """删除知识库模型配置"""

        # 解析复合ID
        real_config_id, target_model_type = self._parse_composite_config_id(config_id)

        config = db.query(KBModelConfig).filter(
            KBModelConfig.id == real_config_id
        ).first()

        if not config:
            return False

        # 验证知识库所有权
        if config.knowledge_base.owner_id != user_id:
            raise ValueError("无权限删除此配置")

        # 如果指定了特定的模型类型，只删除该类型的配置
        if target_model_type:
            if target_model_type == 'embedding':
                config.embedding_model_name = None
                config.embedding_credential_id = None
                config.embedding_config_params = {}
            elif target_model_type == 'reranker':
                config.reranker_model_name = None
                config.reranker_credential_id = None
                config.reranker_config_params = {}
            elif target_model_type == 'llm':
                config.llm_model_name = None
                config.llm_credential_id = None
                config.llm_config_params = {}
            elif target_model_type == 'vlm':
                config.vlm_model_name = None
                config.vlm_credential_id = None
                config.vlm_config_params = {}

            # 检查是否还有其他类型的配置，如果都为空则删除整个记录
            has_any_config = (
                (config.embedding_model_name and config.embedding_credential_id) or
                (config.reranker_model_name and config.reranker_credential_id) or
                (config.llm_model_name and config.llm_credential_id) or
                (config.vlm_model_name and config.vlm_credential_id)
            )

            if not has_any_config:
                db.delete(config)
            else:
                config.updated_at = datetime.utcnow()
        else:
            # 如果没有指定模型类型，删除整个配置记录
            db.delete(config)

        db.commit()
        return True


# 创建服务实例
credential_service = CredentialService()