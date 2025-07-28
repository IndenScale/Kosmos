#!/usr/bin/env python3
"""
数据迁移脚本：将 knowledge_bases 表中的 tag_directory_config 字段重命名为 tag_dictionary
同时将 last_tag_directory_update_time 重命名为 last_tag_dictionary_update_time

使用方法：
python migrate_tag_dictionary_field.py
"""

import os
import sys
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def get_db_connection():
    """获取数据库连接"""
    try:
        connection = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            database=os.getenv("POSTGRES_DB", "kosmos"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "postgres")
        )
        return connection
    except Exception as e:
        print(f"数据库连接失败: {e}")
        sys.exit(1)

def check_column_exists(cursor, table_name, column_name):
    """检查列是否存在"""
    cursor.execute("""
        SELECT EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = %s AND column_name = %s
        );
    """, (table_name, column_name))
    return cursor.fetchone()[0]

def migrate_tag_dictionary_field():
    """执行字段迁移"""
    connection = get_db_connection()
    cursor = connection.cursor()
    
    try:
        print("开始数据迁移...")
        
        # 检查旧字段是否存在
        has_old_tag_field = check_column_exists(cursor, 'knowledge_bases', 'tag_directory_config')
        has_old_time_field = check_column_exists(cursor, 'knowledge_bases', 'last_tag_directory_update_time')
        
        # 检查新字段是否已存在
        has_new_tag_field = check_column_exists(cursor, 'knowledge_bases', 'tag_dictionary')
        has_new_time_field = check_column_exists(cursor, 'knowledge_bases', 'last_tag_dictionary_update_time')
        
        print(f"旧字段状态:")
        print(f"  tag_directory_config: {'存在' if has_old_tag_field else '不存在'}")
        print(f"  last_tag_directory_update_time: {'存在' if has_old_time_field else '不存在'}")
        print(f"新字段状态:")
        print(f"  tag_dictionary: {'存在' if has_new_tag_field else '不存在'}")
        print(f"  last_tag_dictionary_update_time: {'存在' if has_new_time_field else '不存在'}")
        
        # 迁移 tag_directory_config -> tag_dictionary
        if has_old_tag_field:
            if not has_new_tag_field:
                print("1. 重命名 tag_directory_config 为 tag_dictionary...")
                cursor.execute("""
                    ALTER TABLE knowledge_bases 
                    RENAME COLUMN tag_directory_config TO tag_dictionary;
                """)
                print("   ✓ tag_dictionary 字段重命名完成")
            else:
                print("1. 迁移 tag_directory_config 数据到 tag_dictionary...")
                # 如果新字段已存在，复制数据然后删除旧字段
                cursor.execute("""
                    UPDATE knowledge_bases 
                    SET tag_dictionary = tag_directory_config 
                    WHERE tag_dictionary IS NULL AND tag_directory_config IS NOT NULL;
                """)
                cursor.execute("ALTER TABLE knowledge_bases DROP COLUMN tag_directory_config;")
                print("   ✓ 数据迁移完成，旧字段已删除")
        else:
            if not has_new_tag_field:
                print("1. 创建 tag_dictionary 字段...")
                cursor.execute("""
                    ALTER TABLE knowledge_bases 
                    ADD COLUMN tag_dictionary TEXT DEFAULT '{}';
                """)
                print("   ✓ tag_dictionary 字段创建完成")
            else:
                print("1. tag_dictionary 字段已存在，跳过")
        
        # 迁移 last_tag_directory_update_time -> last_tag_dictionary_update_time
        if has_old_time_field:
            if not has_new_time_field:
                print("2. 重命名 last_tag_directory_update_time 为 last_tag_dictionary_update_time...")
                cursor.execute("""
                    ALTER TABLE knowledge_bases 
                    RENAME COLUMN last_tag_directory_update_time TO last_tag_dictionary_update_time;
                """)
                print("   ✓ last_tag_dictionary_update_time 字段重命名完成")
            else:
                print("2. 迁移 last_tag_directory_update_time 数据到 last_tag_dictionary_update_time...")
                cursor.execute("""
                    UPDATE knowledge_bases 
                    SET last_tag_dictionary_update_time = last_tag_directory_update_time 
                    WHERE last_tag_dictionary_update_time IS NULL AND last_tag_directory_update_time IS NOT NULL;
                """)
                cursor.execute("ALTER TABLE knowledge_bases DROP COLUMN last_tag_directory_update_time;")
                print("   ✓ 数据迁移完成，旧字段已删除")
        else:
            if not has_new_time_field:
                print("2. 创建 last_tag_dictionary_update_time 字段...")
                cursor.execute("""
                    ALTER TABLE knowledge_bases 
                    ADD COLUMN last_tag_dictionary_update_time TIMESTAMP;
                """)
                print("   ✓ last_tag_dictionary_update_time 字段创建完成")
            else:
                print("2. last_tag_dictionary_update_time 字段已存在，跳过")
        
        # 提交事务
        connection.commit()
        print("\n✅ 数据迁移完成！")
        
        # 验证迁移结果
        print("\n验证迁移结果:")
        cursor.execute("SELECT COUNT(*) FROM knowledge_bases;")
        total_count = cursor.fetchone()[0]
        print(f"  知识库总数: {total_count}")
        
        if total_count > 0:
            cursor.execute("""
                SELECT COUNT(*) FROM knowledge_bases 
                WHERE tag_dictionary IS NOT NULL AND tag_dictionary != '';
            """)
            tag_count = cursor.fetchone()[0]
            print(f"  有标签字典的知识库: {tag_count}")
        
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        connection.rollback()
        sys.exit(1)
    finally:
        cursor.close()
        connection.close()

if __name__ == "__main__":
    print("Kosmos 数据库字段迁移脚本")
    print("=" * 50)
    
    # 确认执行
    response = input("确认执行数据迁移？(y/N): ")
    if response.lower() != 'y':
        print("迁移已取消")
        sys.exit(0)
    
    migrate_tag_dictionary_field()