#!/usr/bin/env python3
"""
PostgreSQL 数据库迁移脚本 - 添加 updated_at 字段到 fragments 表
文件: run_add_updated_at_migration.py
创建时间: 2025-07-26
描述: 执行 PostgreSQL 数据库迁移，为 fragments 表添加 updated_at 字段
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

def check_table_exists(cursor, table_name):
    """检查表是否存在"""
    cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_name = %s
    """, (table_name,))
    return cursor.fetchone() is not None

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

        # 检查 fragments 表是否存在
        if not check_table_exists(cursor, 'fragments'):
            print("表 fragments 不存在，跳过迁移")
            return True

        # 检查 updated_at 列是否已存在
        if check_column_exists(cursor, 'fragments', 'updated_at'):
            print("列 updated_at 已存在，跳过迁移")
            return True

        print("开始执行迁移...")

        # 读取迁移脚本
        script_path = os.path.join(os.path.dirname(__file__), 'add_updated_at_to_fragments.sql')
        with open(script_path, 'r', encoding='utf-8') as f:
            migration_sql = f.read()

        # 分割SQL语句并逐条执行
        statements = []
        current_statement = ""
        in_function = False

        for line in migration_sql.split('\n'):
            line = line.strip()
            if not line or line.startswith('--'):
                continue

            current_statement += line + " "

            # 检查是否是函数定义
            if 'CREATE OR REPLACE FUNCTION' in line:
                in_function = True
            elif in_function and line.endswith('$$ LANGUAGE plpgsql;'):
                in_function = False
                statements.append(current_statement.strip())
                current_statement = ""
            elif not in_function and line.endswith(';'):
                statements.append(current_statement.strip())
                current_statement = ""

        # 执行每条语句
        for i, statement in enumerate(statements):
            if statement:
                print(f"执行语句 {i+1}/{len(statements)}: {statement[:50]}...")
                try:
                    cursor.execute(statement)
                    conn.commit()
                except psycopg2.Error as e:
                    if "already exists" in str(e) or "does not exist" in str(e):
                        print(f"  跳过（已存在或不存在）: {e}")
                        conn.rollback()
                    else:
                        raise

        conn.commit()
        print("迁移完成！")

        # 验证迁移结果
        if check_column_exists(cursor, 'fragments', 'updated_at'):
            print("✓ updated_at 字段已成功添加到 fragments 表")
        else:
            print("✗ updated_at 字段添加失败")
            return False

        # 检查现有记录的 updated_at 字段
        cursor.execute("SELECT COUNT(*) FROM fragments WHERE updated_at IS NULL")
        null_count = cursor.fetchone()[0]
        if null_count == 0:
            print("✓ 所有现有记录的 updated_at 字段都已正确设置")
        else:
            print(f"⚠ 发现 {null_count} 条记录的 updated_at 字段为空")

        return True

    except psycopg2.Error as e:
        print(f"迁移失败: {e}")
        conn.rollback()
        return False
    except Exception as e:
        print(f"执行迁移时发生错误: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def main():
    """主函数"""
    print("=" * 50)
    print("Fragments 表 updated_at 字段迁移脚本")
    print("=" * 50)

    success = run_migration()

    if success:
        print("\n✓ 迁移成功完成！")
        print("现在可以重新启动应用程序。")
    else:
        print("\n✗ 迁移失败！")
        print("请检查错误信息并重试。")

    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)