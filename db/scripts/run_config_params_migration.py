#!/usr/bin/env python3
"""
运行知识库模型配置参数字段迁移脚本
为 kb_model_configs 表添加各种模型类型的配置参数字段
"""

import os
import sys
import psycopg2
from psycopg2 import sql
import logging
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_db_connection():
    """获取数据库连接"""
    try:
        # 从环境变量获取数据库配置（与database.py保持一致）
        db_config = {
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'port': os.getenv('POSTGRES_PORT', '5432'),
            'database': os.getenv('POSTGRES_DB', 'kosmos'),
            'user': os.getenv('POSTGRES_USER', 'postgres'),
            'password': os.getenv('POSTGRES_PASSWORD', 'postgres')
        }
        
        logger.info(f"连接数据库: {db_config['host']}:{db_config['port']}/{db_config['database']}")
        
        conn = psycopg2.connect(**db_config)
        conn.autocommit = True  # 启用自动提交
        return conn
        
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        raise

def read_migration_sql():
    """读取迁移SQL文件"""
    sql_file = Path(__file__).parent / 'add_config_params_to_kb_model_configs.sql'
    
    if not sql_file.exists():
        raise FileNotFoundError(f"迁移SQL文件不存在: {sql_file}")
    
    with open(sql_file, 'r', encoding='utf-8') as f:
        return f.read()

def check_table_exists(cursor, table_name):
    """检查表是否存在"""
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = %s
        );
    """, (table_name,))
    
    return cursor.fetchone()[0]

def get_current_columns(cursor, table_name):
    """获取表的当前列信息"""
    cursor.execute("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns 
        WHERE table_name = %s 
        AND table_schema = 'public'
        ORDER BY ordinal_position;
    """, (table_name,))
    
    return cursor.fetchall()

def run_migration():
    """运行迁移"""
    conn = None
    try:
        # 获取数据库连接
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 检查目标表是否存在
        if not check_table_exists(cursor, 'kb_model_configs'):
            logger.error("目标表 'kb_model_configs' 不存在，请先创建该表")
            return False
        
        logger.info("目标表 'kb_model_configs' 存在，开始迁移...")
        
        # 显示迁移前的表结构
        logger.info("迁移前的表结构:")
        columns = get_current_columns(cursor, 'kb_model_configs')
        for col in columns:
            logger.info(f"  {col[0]} ({col[1]}) - nullable: {col[2]}, default: {col[3]}")
        
        # 读取并执行迁移SQL
        migration_sql = read_migration_sql()
        logger.info("开始执行迁移SQL...")
        
        # 分割SQL语句并逐个执行（按分号分割，但保留DO块的完整性）
        sql_statements = []
        current_statement = ""
        in_do_block = False
        
        for line in migration_sql.split('\n'):
            line = line.strip()
            if not line or line.startswith('--'):
                continue
                
            current_statement += line + '\n'
            
            # 检测DO块的开始和结束
            if line.startswith('DO $$'):
                in_do_block = True
            elif line == 'END $$;':
                in_do_block = False
                sql_statements.append(current_statement.strip())
                current_statement = ""
            elif not in_do_block and line.endswith(';'):
                sql_statements.append(current_statement.strip())
                current_statement = ""
        
        # 添加最后一个语句（如果有）
        if current_statement.strip():
            sql_statements.append(current_statement.strip())
        
        for i, statement in enumerate(sql_statements):
            if not statement:
                continue
                
            try:
                logger.info(f"执行SQL语句 {i+1}...")
                cursor.execute(statement)
                
                # 获取执行结果中的NOTICE消息
                for notice in conn.notices:
                    logger.info(f"数据库通知: {notice.strip()}")
                conn.notices.clear()
                
            except Exception as e:
                logger.error(f"执行SQL语句 {i+1} 失败: {e}")
                logger.error(f"失败的SQL: {statement[:200]}...")
                raise
        
        # 显示迁移后的表结构
        logger.info("迁移后的表结构:")
        columns = get_current_columns(cursor, 'kb_model_configs')
        for col in columns:
            logger.info(f"  {col[0]} ({col[1]}) - nullable: {col[2]}, default: {col[3]}")
        
        # 验证新字段是否添加成功
        new_columns = ['embedding_config_params', 'reranker_config_params', 'llm_config_params', 'vlm_config_params']
        existing_columns = [col[0] for col in columns]
        
        success_count = 0
        for col_name in new_columns:
            if col_name in existing_columns:
                logger.info(f"✅ 字段 '{col_name}' 添加成功")
                success_count += 1
            else:
                logger.error(f"❌ 字段 '{col_name}' 添加失败")
        
        if success_count == len(new_columns):
            logger.info("🎉 所有配置参数字段迁移成功！")
            return True
        else:
            logger.error(f"⚠️ 只有 {success_count}/{len(new_columns)} 个字段迁移成功")
            return False
            
    except Exception as e:
        logger.error(f"迁移失败: {e}")
        return False
        
    finally:
        if conn:
            conn.close()
            logger.info("数据库连接已关闭")

def main():
    """主函数"""
    logger.info("开始知识库模型配置参数字段迁移...")
    
    try:
        success = run_migration()
        
        if success:
            logger.info("✅ 迁移完成！")
            sys.exit(0)
        else:
            logger.error("❌ 迁移失败！")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("迁移被用户中断")
        sys.exit(1)
    except Exception as e:
        logger.error(f"迁移过程中发生未预期的错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()