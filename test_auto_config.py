#!/usr/bin/env python3
"""测试自动配置功能

该脚本用于测试知识库自动配置功能，包括：
1. 配置文件读取
2. 凭证创建和验证
3. 知识库自动配置
4. 标签字典设置
"""

import os
import sys
import json
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).parent))

from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services.config_service import config_service
from app.services.credential_service import credential_service
from app.services.kb_service import KBService
from app.models.user import User
from app.schemas.knowledge_base import KBCreate
from app.schemas.credential import CredentialCreate, ModelType

def test_config_loading():
    """测试配置文件加载"""
    print("=== 测试配置文件加载 ===")
    
    # 测试用户ID
    test_user_id = "test_user_001"
    
    # 加载配置
    config = config_service.load_user_config(test_user_id)
    if config:
        print(f"✓ 成功加载配置文件")
        print(f"  - 模型配置数量: {len(config.get('models', {}))}")
        print(f"  - 系统配置: {config.get('system', {})}")
    else:
        print(f"✗ 配置文件加载失败")
        return False
    
    # 测试标签字典
    tag_dict = config_service.get_default_tag_dictionary(test_user_id)
    if tag_dict:
        print(f"✓ 成功解析标签字典，包含 {len(tag_dict)} 个分类")
        for category, tags in tag_dict.items():
            print(f"  - {category}: {len(tags)} 个标签")
    else:
        print(f"✗ 标签字典解析失败")
    
    # 测试模型配置
    models_config = config_service.get_model_configs(test_user_id)
    print(f"✓ 模型配置: {list(models_config.keys())}")
    
    return True

def test_credential_creation():
    """测试凭证创建"""
    print("\n=== 测试凭证创建 ===")
    
    # 获取数据库会话
    db = next(get_db())
    
    try:
        # 创建测试用户（如果不存在）
        test_user_id = "test_user_001"
        test_user = db.query(User).filter(User.id == test_user_id).first()
        
        if not test_user:
            test_user = User(
                id=test_user_id,
                username="test_user",
                email="test@example.com",
                hashed_password="dummy_hash"
            )
            db.add(test_user)
            db.commit()
            print(f"✓ 创建测试用户: {test_user_id}")
        
        # 测试凭证创建
        credential_data = CredentialCreate(
            name="Test Embedding Credential",
            provider="openai",
            model_type=ModelType.EMBEDDING,
            api_key="test_api_key_123",
            base_url="https://api.openai.com/v1",
            description="测试用凭证"
        )
        
        credential = credential_service.create_credential(
            db, test_user_id, credential_data
        )
        
        print(f"✓ 成功创建凭证: {credential.id}")
        print(f"  - 名称: {credential.name}")
        print(f"  - 提供商: {credential.provider}")
        print(f"  - 模型类型: {credential.model_type}")
        
        return credential.id
        
    except Exception as e:
        print(f"✗ 凭证创建失败: {e}")
        return None
    finally:
        db.close()

def test_improved_config_format(credential_id):
    """测试改进的配置格式"""
    print("\n=== 测试改进的配置格式 ===")
    
    if not credential_id:
        print("✗ 需要有效的凭证ID")
        return False
    
    # 创建改进格式的配置文件
    test_user_id = "test_user_001"
    config_path = Path(f"/home/sdf/AssessmentSystem_v2/Kosmos/config/{test_user_id}_defaults.toml")
    
    improved_config = f"""# 测试用改进配置
[tag_dictionary]
default_tag_directory = '''
{{
  "测试分类": ["标签1", "标签2", "标签3"]
}}
'''

[models.embedding]
model_name = "text-embedding-3-small"
credential_id = "{credential_id}"
config_params = {{dimensions = 1536}}

[system]
auto_create_models = true
auto_set_tags = true
overwrite_existing = false
"""
    
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(improved_config)
        print(f"✓ 创建测试配置文件: {config_path}")
        
        # 测试新格式读取
        db = next(get_db())
        try:
            credential_id_map = config_service.get_credential_ids_from_config(
                db, test_user_id
            )
            
            if credential_id_map:
                print(f"✓ 成功读取凭证ID映射: {credential_id_map}")
                return True
            else:
                print(f"✗ 凭证ID映射为空")
                return False
        finally:
            db.close()
            
    except Exception as e:
        print(f"✗ 测试改进配置格式失败: {e}")
        return False

def test_auto_kb_creation():
    """测试自动知识库创建"""
    print("\n=== 测试自动知识库创建 ===")
    
    db = next(get_db())
    
    try:
        # 获取测试用户
        test_user_id = "test_user_001"
        test_user = db.query(User).filter(User.id == test_user_id).first()
        
        if not test_user:
            print(f"✗ 测试用户不存在")
            return False
        
        # 创建知识库服务
        kb_service = KBService(db)
        
        # 创建知识库
        kb_data = KBCreate(
            name="测试自动配置知识库",
            description="用于测试自动配置功能的知识库",
            is_public=False
        )
        
        kb = kb_service.create_kb(kb_data, test_user)
        
        print(f"✓ 成功创建知识库: {kb.id}")
        print(f"  - 名称: {kb.name}")
        print(f"  - 描述: {kb.description}")
        
        # 检查标签字典是否自动设置
        if kb.tag_dictionary:
            tag_dict = json.loads(kb.tag_dictionary)
            print(f"✓ 自动设置标签字典，包含 {len(tag_dict)} 个分类")
        else:
            print(f"! 标签字典未自动设置")
        
        # 检查模型配置是否自动创建
        kb_with_configs = kb_service.get_kb_with_model_configs(kb.id, test_user_id)
        if kb_with_configs and kb_with_configs.get('model_configs'):
            model_configs = kb_with_configs['model_configs']
            print(f"✓ 自动创建模型配置")
            print(f"  - 配置数量: {len(model_configs.configs)}")
        else:
            print(f"! 模型配置未自动创建")
        
        return True
        
    except Exception as e:
        print(f"✗ 自动知识库创建失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

def main():
    """主测试函数"""
    print("开始测试知识库自动配置功能\n")
    
    # 1. 测试配置文件加载
    if not test_config_loading():
        print("\n配置文件加载测试失败，退出")
        return
    
    # 2. 测试凭证创建
    credential_id = test_credential_creation()
    if not credential_id:
        print("\n凭证创建测试失败，退出")
        return
    
    # 3. 测试改进的配置格式
    if not test_improved_config_format(credential_id):
        print("\n改进配置格式测试失败")
    
    # 4. 测试自动知识库创建
    if not test_auto_kb_creation():
        print("\n自动知识库创建测试失败")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    main()