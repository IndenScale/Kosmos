#!/usr/bin/env python3
"""
PostgreSQL 数据库迁移脚本
文件: run_pg_migration.py
创建时间: 2025-07-26
描述: 执行 PostgreSQL 数据库迁移，添加 model_type 字段
"""

import os
import sys
import psycopg2
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def get_db_connection():
    """获取数据库连接"""
    try:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            database=os.getenv("POSTGRES_DB", "kosmos"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "postgres")
        )
        return conn
    except psycopg2.Error as e:
        print(f"数据库连接失败: {e}")
        return None

def check_column_exists(cursor, table_name, column_name):
    """检查列是否存在"""
    cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
    """, (table_name, column_name))
    return cursor.fetchone() is not None

def run_migration():
    """执行迁移"""
    conn = get_db_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()

        # 检查表是否存在
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_name = 'model_access_credentials'
        """)

        if not cursor.fetchone():
            print("表 model_access_credentials 不存在，跳过迁移")
            return True

        # 检查 model_type 列是否已存在
        if check_column_exists(cursor, 'model_access_credentials', 'model_type'):
            print("列 model_type 已存在，跳过迁移")
            return True

        print("开始执行迁移...")

        # 读取迁移脚本
        script_path = os.path.join(os.path.dirname(__file__), 'add_model_type_to_credentials.sql')
        with open(script_path, 'r', encoding='utf-8') as f:
            migration_sql = f.read()

        # 执行迁移
        statements = [stmt.strip() for stmt in migration_sql.split(';') if stmt.strip() and not stmt.strip().startswith('--')]

        for statement in statements:
            if statement:
                print(f"执行: {statement[:50]}...")
                cursor.execute(statement)

        conn.commit()
        print("迁移完成！")
        return True

    except psycopg2.Error as e:
        print(f"迁移失败: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)