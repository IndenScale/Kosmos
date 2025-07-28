#!/usr/bin/env python3
"""
为 index_entries 表添加 CASCADE DELETE 外键约束的迁移脚本
文件: run_cascade_delete_migration.py
创建时间: 2025-07-26
描述: 执行数据库迁移，修复外键约束问题
"""

import os
import sys
import logging
import psycopg2
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_db_connection():
    """获取数据库连接"""
    try:
        # 从环境变量获取数据库配置
        db_config = {
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'port': os.getenv('POSTGRES_PORT', '5432'),
            'database': os.getenv('POSTGRES_DB', 'kosmos'),
            'user': os.getenv('POSTGRES_USER', 'postgres'),
            'password': os.getenv('POSTGRES_PASSWORD', 'postgres')
        }

        logger.info(f"连接数据库: {db_config['host']}:{db_config['port']}/{db_config['database']}")

        conn = psycopg2.connect(**db_config)
        conn.autocommit = True
        return conn

    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        raise

def check_current_constraint(cursor):
    """检查当前的外键约束"""
    logger.info("检查当前的外键约束...")

    cursor.execute("""
        SELECT
            tc.constraint_name,
            tc.table_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name,
            rc.delete_rule
        FROM
            information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
              AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
              AND ccu.table_schema = tc.table_schema
            JOIN information_schema.referential_constraints AS rc
              ON tc.constraint_name = rc.constraint_name
              AND tc.table_schema = rc.constraint_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_name = 'index_entries'
          AND kcu.column_name = 'fragment_id';
    """)

    result = cursor.fetchone()
    if result:
        constraint_name, table_name, column_name, foreign_table, foreign_column, delete_rule = result
        logger.info(f"找到现有约束: {constraint_name}, 删除规则: {delete_rule}")
        return constraint_name, delete_rule
    else:
        logger.info("未找到现有的 fragment_id 外键约束")
        return None, None

def drop_existing_constraint(cursor, constraint_name):
    """删除现有的外键约束"""
    if constraint_name:
        logger.info(f"删除现有外键约束: {constraint_name}")
        cursor.execute(f"ALTER TABLE index_entries DROP CONSTRAINT {constraint_name};")
        logger.info("✅ 现有约束已删除")

def add_cascade_constraint(cursor):
    """添加新的CASCADE外键约束"""
    logger.info("添加新的 CASCADE DELETE 外键约束...")

    cursor.execute("""
        ALTER TABLE index_entries
        ADD CONSTRAINT fk_index_entries_fragment_id
        FOREIGN KEY (fragment_id)
        REFERENCES fragments(id)
        ON DELETE CASCADE;
    """)

    logger.info("✅ 新的 CASCADE DELETE 约束已添加")

def verify_constraint(cursor):
    """验证新的外键约束"""
    logger.info("验证新的外键约束...")

    cursor.execute("""
        SELECT
            tc.constraint_name,
            rc.delete_rule
        FROM
            information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.referential_constraints AS rc
              ON tc.constraint_name = rc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_name = 'index_entries'
          AND kcu.column_name = 'fragment_id';
    """)

    result = cursor.fetchone()
    if result:
        constraint_name, delete_rule = result
        logger.info(f"✅ 验证成功: {constraint_name}, 删除规则: {delete_rule}")
        return delete_rule == 'CASCADE'
    else:
        logger.error("❌ 验证失败: 未找到外键约束")
        return False

def add_comment(cursor):
    """添加约束注释"""
    cursor.execute("""
        COMMENT ON CONSTRAINT fk_index_entries_fragment_id ON index_entries IS
        '外键约束：当删除 fragments 时自动删除相关的 index_entries，解决解析时的外键约束违反问题';
    """)
    logger.info("✅ 约束注释已添加")

def main():
    """主函数"""
    logger.info("开始执行 index_entries CASCADE DELETE 迁移...")

    try:
        # 连接数据库
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. 检查当前约束
        constraint_name, delete_rule = check_current_constraint(cursor)

        # 如果已经是CASCADE，则跳过
        if delete_rule == 'CASCADE':
            logger.info("✅ 外键约束已经是 CASCADE DELETE，无需迁移")
            return

        # 2. 删除现有约束
        drop_existing_constraint(cursor, constraint_name)

        # 3. 添加新的CASCADE约束
        add_cascade_constraint(cursor)

        # 4. 验证约束
        if verify_constraint(cursor):
            logger.info("✅ 迁移成功完成")
        else:
            logger.error("❌ 迁移验证失败")
            sys.exit(1)

        # 5. 添加注释
        add_comment(cursor)

        logger.info("🎉 index_entries CASCADE DELETE 迁移已完成")

    except Exception as e:
        logger.error(f"迁移失败: {e}")
        sys.exit(1)

    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    main()