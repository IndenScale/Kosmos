"""配置服务
文件: config_service.py
创建时间: 2025-01-27
描述: 读取和处理用户默认配置文件，支持自动配置知识库
"""

import os
import toml
import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.credential import ModelAccessCredential
from app.schemas.credential import ModelType, CredentialCreate
from app.services.credential_service import CredentialService

logger = logging.getLogger(__name__)

class ConfigService:
    """配置服务类"""
    
    def __init__(self):
        self.credential_service = CredentialService()
        # 使用相对于当前文件路径的配置目录
        project_root = Path(__file__).parent.parent.parent
        self.config_dir = project_root / "config"
    
    def get_user_config_path(self, user_id: str) -> Path:
        """获取用户配置文件路径"""
        return self.config_dir / f"{user_id}_defaults.toml"
    
    def load_user_config(self, user_id: str) -> Optional[Dict[str, Any]]:
        """加载用户配置文件"""
        config_path = self.get_user_config_path(user_id)
        
        if not config_path.exists():
            logger.warning(f"配置文件不存在: {config_path}")
            return None
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = toml.load(f)
            logger.info(f"成功加载配置文件: {config_path}")
            return config
        except Exception as e:
            logger.error(f"加载配置文件失败 {config_path}: {e}")
            return None
    
    def get_default_tag_dictionary(self, user_id: str) -> Optional[Dict[str, List[str]]]:
        """获取默认标签字典"""
        config = self.load_user_config(user_id)
        if not config:
            return None
        
        try:
            tag_dict_str = config.get('tag_dictionary', {}).get('default_tag_directory', '')
            if tag_dict_str:
                # 解析JSON格式的标签字典
                tag_dict = json.loads(tag_dict_str)
                return tag_dict
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"解析标签字典失败: {e}")
        
        return None
    
    def get_model_configs(self, user_id: str) -> Dict[str, Dict[str, Any]]:
        """获取模型配置"""
        config = self.load_user_config(user_id)
        if not config:
            return {}
        
        models_config = config.get('models', {})
        return models_config
    
    def get_system_config(self, user_id: str) -> Dict[str, Any]:
        """获取系统配置"""
        config = self.load_user_config(user_id)
        if not config:
            return {}
        
        system_config = config.get('system', {})
        return {
            'auto_create_models': system_config.get('auto_create_models', False),
            'auto_set_tags': system_config.get('auto_set_tags', False),
            'overwrite_existing': system_config.get('overwrite_existing', False)
        }
    
    def get_credential_ids_from_config(
        self, 
        db: Session, 
        user_id: str
    ) -> Dict[str, str]:
        """从配置文件获取凭证ID映射（新格式）"""
        models_config = self.get_model_configs(user_id)
        credential_id_map = {}
        
        for model_key, model_config in models_config.items():
            if model_key not in ['embedding', 'reranker', 'llm', 'vlm']:
                continue
            
            # 检查是否使用新的凭证ID引用格式
            if 'credential_id' in model_config:
                credential_id = model_config['credential_id']
                
                # 验证凭证是否存在且属于当前用户
                credential = self.credential_service.get_credential_by_id(
                    db, credential_id, user_id
                )
                
                if credential:
                    credential_id_map[model_key] = credential_id
                    logger.info(f"使用配置的凭证ID {credential_id} for {model_key}")
                else:
                    logger.warning(f"凭证ID {credential_id} 不存在或不属于用户 {user_id}")
            else:
                logger.warning(f"模型配置 {model_key} 未指定credential_id")
        
        return credential_id_map
    
    def create_credentials_from_config(
        self, 
        db: Session, 
        user_id: str, 
        overwrite_existing: bool = False
    ) -> Dict[str, str]:
        """从配置文件创建凭证，返回凭证ID映射（兼容旧格式）"""
        # 首先尝试新格式（凭证ID引用）
        credential_id_map = self.get_credential_ids_from_config(db, user_id)
        if credential_id_map:
            return credential_id_map
        
        # 回退到旧格式（直接包含API密钥）
        logger.warning(f"用户 {user_id} 使用旧格式配置文件，建议升级到凭证ID引用格式")
        
        models_config = self.get_model_configs(user_id)
        credential_id_map = {}
        
        # 模型类型映射
        model_type_map = {
            'embedding': ModelType.EMBEDDING,
            'reranker': ModelType.RERANKER,
            'llm': ModelType.LLM,
            'vlm': ModelType.VLM
        }
        
        for model_key, model_config in models_config.items():
            if model_key not in model_type_map:
                continue
            
            model_type = model_type_map[model_key]
            
            # 检查必要字段
            if not all(key in model_config for key in ['model_name', 'provider', 'api_key']):
                logger.warning(f"模型配置 {model_key} 缺少必要字段，跳过")
                continue
            
            # 检查是否已存在相同的凭证
            existing_credentials = self.credential_service.get_user_credentials(
                db, user_id, model_type
            )
            
            credential_name = f"Auto-{model_config['model_name']}-{model_config['provider']}"
            
            # 查找是否已有同名凭证
            existing_credential = None
            for cred in existing_credentials:
                if cred.name == credential_name:
                    existing_credential = cred
                    break
            
            if existing_credential and not overwrite_existing:
                logger.info(f"凭证 {credential_name} 已存在，跳过创建")
                credential_id_map[model_key] = existing_credential.id
                continue
            
            try:
                # 创建凭证数据
                credential_data = CredentialCreate(
                    name=credential_name,
                    provider=model_config['provider'],
                    model_type=model_type,
                    api_key=model_config['api_key'],
                    base_url=model_config.get('base_url'),
                    description=f"从配置文件自动创建的{model_key}模型凭证"
                )
                
                if existing_credential and overwrite_existing:
                    # 更新现有凭证
                    updated_credential = self.credential_service.update_credential(
                        db, existing_credential.id, user_id, credential_data
                    )
                    if updated_credential:
                        credential_id_map[model_key] = updated_credential.id
                        logger.info(f"更新凭证: {credential_name}")
                else:
                    # 创建新凭证
                    new_credential = self.credential_service.create_credential(
                        db, user_id, credential_data
                    )
                    credential_id_map[model_key] = new_credential.id
                    logger.info(f"创建凭证: {credential_name}")
                    
            except Exception as e:
                logger.error(f"创建/更新凭证 {credential_name} 失败: {e}")
                continue
        
        return credential_id_map
    
    def get_model_config_params(self, user_id: str, model_key: str) -> Dict[str, Any]:
        """获取模型配置参数"""
        models_config = self.get_model_configs(user_id)
        model_config = models_config.get(model_key, {})
        return model_config.get('config_params', {})
    
    def should_auto_configure(self, user_id: str) -> bool:
        """检查是否应该自动配置"""
        system_config = self.get_system_config(user_id)
        return system_config.get('auto_create_models', False)

# 全局配置服务实例
config_service = ConfigService()