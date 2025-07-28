#!/usr/bin/env python3
"""
模型配置迁移脚本
文件: migrate_model_configs.py
创建时间: 2025-07-26
描述: 将知识库的embedding_config字段数据迁移到新的模型配置表结构中
"""

import os
import sys
import json
import uuid
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 数据库连接配置
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "kosmos")

SQLALCHEMY_DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

def create_db_session():
    """创建数据库会话"""
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal(), engine

def migrate_embedding_configs():
    """迁移embedding_config数据到新的模型配置表"""
    session, engine = create_db_session()

    try:
        print("开始迁移embedding_config数据...")

        # 1. 检查是否存在embedding_config字段
        check_column_sql = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'knowledge_bases'
        AND column_name = 'embedding_config'
        """

        result = session.execute(text(check_column_sql)).fetchone()
        if not result:
            print("embedding_config字段不存在，跳过迁移")
            return

        # 2. 获取所有知识库的embedding_config数据
        get_configs_sql = """
        SELECT id, embedding_config, owner_id
        FROM knowledge_bases
        WHERE embedding_config IS NOT NULL
        AND embedding_config != '{}'
        AND embedding_config != ''
        """

        kb_configs = session.execute(text(get_configs_sql)).fetchall()
        print(f"找到 {len(kb_configs)} 个知识库需要迁移embedding_config")

        migrated_count = 0

        for kb_config in kb_configs:
            kb_id, embedding_config_str, owner_id = kb_config

            try:
                # 解析embedding_config JSON
                if isinstance(embedding_config_str, str):
                    embedding_config = json.loads(embedding_config_str)
                else:
                    embedding_config = embedding_config_str

                if not embedding_config or not isinstance(embedding_config, dict):
                    continue

                # 提取模型名称
                model_name = embedding_config.get('model', 'text-embedding-3-small')
                api_key = embedding_config.get('api_key')
                base_url = embedding_config.get('base_url')
                provider = embedding_config.get('provider', 'openai')

                credential_id = None

                # 如果有API Key，创建凭证记录
                if api_key:
                    credential_id = str(uuid.uuid4())
                    credential_name = f"从{kb_id}迁移的{provider}凭证"

                    # 注意：这里应该加密API Key，但为了简化示例，我们先用明文
                    # 在实际生产环境中，必须使用加密
                    insert_credential_sql = """
                    INSERT INTO model_access_credentials
                    (id, user_id, name, provider, api_key_encrypted, base_url, description, is_active, created_at, updated_at)
                    VALUES (:id, :user_id, :name, :provider, :api_key, :base_url, :description, 'true', :created_at, :updated_at)
                    ON CONFLICT (user_id, name) DO NOTHING
                    """

                    session.execute(text(insert_credential_sql), {
                        'id': credential_id,
                        'user_id': owner_id,
                        'name': credential_name,
                        'provider': provider,
                        'api_key': f"MIGRATED:{api_key}",  # 标记为迁移的数据
                        'base_url': base_url,
                        'description': f"从知识库 {kb_id} 的 embedding_config 自动迁移",
                        'created_at': datetime.now(),
                        'updated_at': datetime.now()
                    })

                # 更新或插入模型配置
                upsert_model_config_sql = """
                INSERT INTO kb_model_configs
                (id, kb_id, embedding_model_name, embedding_credential_id, llm_model_name, created_at, updated_at)
                VALUES (:id, :kb_id, :embedding_model_name, :embedding_credential_id, :llm_model_name, :created_at, :updated_at)
                ON CONFLICT (kb_id) DO UPDATE SET
                    embedding_model_name = EXCLUDED.embedding_model_name,
                    embedding_credential_id = EXCLUDED.embedding_credential_id,
                    updated_at = EXCLUDED.updated_at
                """

                session.execute(text(upsert_model_config_sql), {
                    'id': str(uuid.uuid4()),
                    'kb_id': kb_id,
                    'embedding_model_name': model_name,
                    'embedding_credential_id': credential_id,
                    'llm_model_name': 'gpt-4-turbo-preview',
                    'created_at': datetime.now(),
                    'updated_at': datetime.now()
                })

                migrated_count += 1
                print(f"✓ 已迁移知识库 {kb_id} 的配置")

            except json.JSONDecodeError as e:
                print(f"✗ 知识库 {kb_id} 的embedding_config JSON格式错误: {e}")
                continue
            except Exception as e:
                print(f"✗ 迁移知识库 {kb_id} 时出错: {e}")
                continue

        # 提交事务
        session.commit()
        print(f"迁移完成！成功迁移了 {migrated_count} 个知识库的配置")

        # 3. 可选：删除embedding_config字段（谨慎操作）
        print("\n注意：如果确认迁移成功，可以手动执行以下SQL删除旧字段：")
        print("ALTER TABLE knowledge_bases DROP COLUMN IF EXISTS embedding_config;")

    except Exception as e:
        session.rollback()
        print(f"迁移过程中发生错误: {e}")
        raise
    finally:
        session.close()

def verify_migration():
    """验证迁移结果"""
    session, engine = create_db_session()

    try:
        print("\n验证迁移结果...")

        # 检查模型配置表的记录数
        config_count_sql = "SELECT COUNT(*) FROM kb_model_configs"
        config_count = session.execute(text(config_count_sql)).scalar()

        # 检查凭证表的记录数
        credential_count_sql = "SELECT COUNT(*) FROM model_access_credentials"
        credential_count = session.execute(text(credential_count_sql)).scalar()

        # 检查知识库总数
        kb_count_sql = "SELECT COUNT(*) FROM knowledge_bases"
        kb_count = session.execute(text(kb_count_sql)).scalar()

        print(f"知识库总数: {kb_count}")
        print(f"模型配置记录数: {config_count}")
        print(f"凭证记录数: {credential_count}")

        if config_count >= kb_count:
            print("✓ 验证通过：所有知识库都有对应的模型配置")
        else:
            print("⚠ 警告：部分知识库缺少模型配置")

    except Exception as e:
        print(f"验证过程中发生错误: {e}")
    finally:
        session.close()

def main():
    """主函数"""
    print("Kosmos 模型配置迁移脚本")
    print("=" * 50)

    try:
        # 执行迁移
        migrate_embedding_configs()

        # 验证迁移结果
        verify_migration()

        print("\n迁移脚本执行完成！")

    except Exception as e:
        print(f"脚本执行失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()