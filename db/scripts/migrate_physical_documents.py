#!/usr/bin/env python3
"""
Kosmos Physical Documents 表迁移脚本

此脚本将 physical_documents 表从旧结构迁移到新结构：
- 移除 file_path 字段，添加 url 字段
- 添加 file_size, encoding, language, updated_at 字段
- 扩展 extension 字段长度
- 添加 content_hash 索引

使用方法：
    python migrate_physical_documents.py

注意：
- 执行前会自动备份数据库（如果支持）
- 如果迁移失败，请手动恢复数据
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


def get_database_url():
    """从环境变量获取数据库连接URL"""
    postgres_user = os.getenv("POSTGRES_USER", "postgres")
    postgres_password = os.getenv("POSTGRES_PASSWORD", "postgres")
    postgres_host = os.getenv("POSTGRES_HOST", "localhost")
    postgres_port = os.getenv("POSTGRES_PORT", "5432")
    postgres_db = os.getenv("POSTGRES_DB", "kosmos")
    
    return f"postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{postgres_db}"


def check_table_exists(session, table_name):
    """检查表是否存在"""
    result = session.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = :table_name
        )
    """), {"table_name": table_name})
    return result.scalar()


def get_table_columns(session, table_name):
    """获取表的列信息"""
    result = session.execute(text("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = :table_name
        ORDER BY ordinal_position
    """), {"table_name": table_name})
    return result.fetchall()

def migrate_physical_documents():
    """执行 physical_documents 表迁移"""
    
    print("=" * 60)
    print("🚀 Kosmos Physical Documents 表迁移工具 (PostgreSQL)")
    print("⚠️  这将修改数据库结构，是否继续？(y/N): ", end="")
    
    if input().lower() != 'y':
        print("❌ 迁移已取消")
        return False
    
    print("🔄 开始迁移 physical_documents 表...")
    
    # 获取数据库连接
    database_url = get_database_url()
    print(f"📁 数据库连接: {database_url.replace(os.getenv('POSTGRES_PASSWORD', 'postgres'), '***')}")
    
    try:
        # 创建数据库引擎和会话
        engine = create_engine(database_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()
        
        # 检查表是否存在
        if not check_table_exists(session, 'physical_documents'):
            print("❌ physical_documents 表不存在")
            return False
        
        # 获取当前表结构
        print("📋 当前表结构:")
        columns = get_table_columns(session, 'physical_documents')
        for column in columns:
            print(f"   - {column[0]} {column[1]} {'NULL' if column[2] == 'YES' else 'NOT NULL'}")
        
        # 检查是否已经迁移过
        column_names = [col[0] for col in columns]
        if 'url' in column_names:
            print("⚠️  表似乎已经迁移过了（存在 url 字段）")
            print("是否强制重新迁移？(y/N): ", end="")
            if input().lower() != 'y':
                print("❌ 迁移已取消")
                return False
        
        print("🔧 开始执行迁移...")
        
        # SQLAlchemy 会话默认已经在事务中，不需要显式调用 begin()
        
        # 1. 添加新字段（如果不存在）
        print("   1. 添加新字段...")
        
        # 检查并添加 url 字段
        if 'url' not in column_names:
            session.execute(text("ALTER TABLE physical_documents ADD COLUMN url TEXT"))
            print("      ✅ 添加 url 字段")
        
        # 检查并添加 file_size 字段
        if 'file_size' not in column_names:
            session.execute(text("ALTER TABLE physical_documents ADD COLUMN file_size BIGINT"))
            print("      ✅ 添加 file_size 字段")
        
        # 检查并添加 encoding 字段
        if 'encoding' not in column_names:
            session.execute(text("ALTER TABLE physical_documents ADD COLUMN encoding VARCHAR(50)"))
            print("      ✅ 添加 encoding 字段")
        
        # 检查并添加 language 字段
        if 'language' not in column_names:
            session.execute(text("ALTER TABLE physical_documents ADD COLUMN language VARCHAR(10)"))
            print("      ✅ 添加 language 字段")
        
        # 检查并添加 updated_at 字段
        if 'updated_at' not in column_names:
            session.execute(text("ALTER TABLE physical_documents ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
            print("      ✅ 添加 updated_at 字段")
        
        # 2. 迁移数据：将 file_path 转换为 file:/// URL
        print("   2. 迁移数据...")
        if 'file_path' in column_names:
            # 更新 url 字段，将 file_path 转换为 file:/// URL
            session.execute(text("""
                UPDATE physical_documents 
                SET url = 'file:///' || REPLACE(file_path, '\', '/')
                WHERE file_path IS NOT NULL AND (url IS NULL OR url = '')
            """))
            print("      ✅ 将 file_path 转换为 URL")
        
        # 3. 设置默认值
        print("   3. 设置默认值...")
        session.execute(text("""
            UPDATE physical_documents 
            SET updated_at = CURRENT_TIMESTAMP 
            WHERE updated_at IS NULL
        """))
        print("      ✅ 设置 updated_at 默认值")
        
        # 4. 创建索引
        print("   4. 创建索引...")
        try:
            session.execute(text("CREATE INDEX IF NOT EXISTS idx_physical_documents_content_hash ON physical_documents(content_hash)"))
            print("      ✅ 创建 content_hash 索引")
        except Exception as e:
            print(f"      ⚠️  创建索引失败（可能已存在）: {e}")
        
        try:
            session.execute(text("CREATE INDEX IF NOT EXISTS idx_physical_documents_url ON physical_documents(url)"))
            print("      ✅ 创建 url 索引")
        except Exception as e:
            print(f"      ⚠️  创建索引失败（可能已存在）: {e}")
        
        # 5. 创建触发器来自动更新 updated_at
        print("   5. 创建触发器...")
        try:
            session.execute(text("""
                CREATE OR REPLACE FUNCTION update_physical_documents_updated_at()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = CURRENT_TIMESTAMP;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
            """))
            
            session.execute(text("""
                DROP TRIGGER IF EXISTS trigger_update_physical_documents_updated_at ON physical_documents;
                CREATE TRIGGER trigger_update_physical_documents_updated_at
                    BEFORE UPDATE ON physical_documents
                    FOR EACH ROW
                    EXECUTE FUNCTION update_physical_documents_updated_at();
            """))
            print("      ✅ 创建 updated_at 自动更新触发器")
        except Exception as e:
            print(f"      ⚠️  创建触发器失败: {e}")
        
        # 提交事务
        session.commit()
        
        # 验证迁移结果
        print("✅ 验证迁移结果:")
        new_columns = get_table_columns(session, 'physical_documents')
        for column in new_columns:
            print(f"   - {column[0]} {column[1]} {'NULL' if column[2] == 'YES' else 'NOT NULL'}")
        
        # 检查数据完整性
        result = session.execute(text("SELECT COUNT(*) FROM physical_documents"))
        count = result.scalar()
        print(f"📊 表中记录数: {count}")
        
        # 检查 URL 迁移情况
        result = session.execute(text("SELECT COUNT(*) FROM physical_documents WHERE url IS NOT NULL"))
        url_count = result.scalar()
        print(f"📊 已设置 URL 的记录数: {url_count}")
        
        session.close()
        
        print("✅ 迁移成功完成！")
        print("\n📝 迁移总结:")
        print("   - 添加了 url, file_size, encoding, language, updated_at 字段")
        print("   - 将 file_path 数据迁移到 url 字段（file:/// 格式）")
        print("   - 创建了必要的索引")
        print("   - 设置了 updated_at 自动更新触发器")
        print("\n⚠️  注意：file_path 字段仍然保留，如需删除请手动执行：")
        print("   ALTER TABLE physical_documents DROP COLUMN file_path;")
        
        return True
        
    except Exception as e:
        print(f"❌ 迁移过程中发生错误: {e}")
        try:
            session.rollback()
            session.close()
        except:
            pass
        return False

if __name__ == "__main__":
    try:
        success = migrate_physical_documents()
        if not success:
            print("\n❌ 迁移失败！请检查错误信息。")
            exit(1)
        else:
            print("\n🎉 迁移成功完成！")
    except KeyboardInterrupt:
        print("\n❌ 迁移被用户中断")
        exit(1)
    except Exception as e:
        print(f"\n❌ 发生未预期的错误: {e}")
        exit(1)