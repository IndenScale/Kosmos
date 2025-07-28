#!/usr/bin/env python3
"""
手动执行数据库迁移脚本
"""

import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def execute_migration():
    try:
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=os.getenv('POSTGRES_PORT', '5432'),
            database=os.getenv('POSTGRES_DB', 'kosmos'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', 'postgres')
        )
        cursor = conn.cursor()
        
        print('开始执行迁移...')
        
        # 检查字段是否已存在
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'model_access_credentials' AND column_name = 'model_type'
        """)
        
        if cursor.fetchone():
            print('model_type 字段已存在，跳过迁移')
            return True
        
        # 添加 model_type 字段
        cursor.execute('ALTER TABLE model_access_credentials ADD COLUMN model_type VARCHAR(20);')
        print('✓ 添加 model_type 字段')
        
        # 为现有记录设置默认值
        cursor.execute("UPDATE model_access_credentials SET model_type = 'embedding' WHERE model_type IS NULL;")
        print('✓ 设置默认值')
        
        # 设置字段为非空
        cursor.execute('ALTER TABLE model_access_credentials ALTER COLUMN model_type SET NOT NULL;')
        print('✓ 设置非空约束')
        
        # 添加检查约束
        cursor.execute("ALTER TABLE model_access_credentials ADD CONSTRAINT chk_model_type CHECK (model_type IN ('embedding', 'reranker', 'llm', 'vlm'));")
        print('✓ 添加检查约束')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_credentials_user_model_type ON model_access_credentials(user_id, model_type);')
        print('✓ 创建索引')
        
        conn.commit()
        print('迁移完成！')
        
        # 验证结果
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'model_access_credentials' AND column_name = 'model_type'
        """)
        
        result = cursor.fetchone()
        if result:
            print(f'验证: model_type 字段已添加 - {result[0]}: {result[1]}, nullable: {result[2]}')
        else:
            print('错误: model_type 字段未找到')
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f'迁移失败: {e}')
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

if __name__ == "__main__":
    success = execute_migration()
    exit(0 if success else 1)