#!/usr/bin/env python3
"""
移除凭证名称唯一约束的数据库迁移脚本
文件: run_remove_constraint_migration.py
创建时间: 2025-07-26
描述: 执行移除凭证名称唯一约束的数据库迁移
"""

import os
import sys
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def get_db_config():
    """获取数据库配置"""
    return {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': os.getenv('POSTGRES_PORT', '5432'),
        'database': os.getenv('POSTGRES_DB', 'kosmos'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', 'postgres')
    }

def run_migration():
    """执行数据库迁移"""
    try:
        # 连接数据库
        db_config = get_db_config()
        print(f"连接数据库: {db_config['host']}:{db_config['port']}/{db_config['database']}")

        conn = psycopg2.connect(**db_config)
        conn.autocommit = True
        cursor = conn.cursor()

        # 读取迁移脚本
        script_path = os.path.join(os.path.dirname(__file__), 'remove_credential_name_constraint.sql')
        with open(script_path, 'r', encoding='utf-8') as f:
            migration_sql = f.read()

        print("执行迁移脚本...")
        cursor.execute(migration_sql)

        print("✅ 数据库迁移完成！")

        cursor.close()
        conn.close()

    except psycopg2.Error as e:
        print(f"❌ 数据库错误: {e}")
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"❌ 文件未找到: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_migration()