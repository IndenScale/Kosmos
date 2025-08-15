#!/usr/bin/env python3
"""
数据库连接测试脚本
用于测试PostgreSQL和Milvus的连接是否正常
"""

import os
import sys
import time
from typing import Tuple

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from pymilvus import connections, utility
except ImportError:
    print("正在安装依赖包...")
    os.system("pip install psycopg2-binary pymilvus python-dotenv")
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from pymilvus import connections, utility

from dotenv import load_dotenv

def load_environment():
    """加载环境变量"""
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"✓ 已加载环境变量文件: {env_path}")
    else:
        print(f"✗ 未找到环境变量文件: {env_path}")
        sys.exit(1)

def test_postgresql_connection() -> Tuple[bool, str]:
    """测试PostgreSQL连接"""
    try:
        # 在宿主机上运行时，使用localhost而不是服务名
        host = 'localhost' if os.getenv('POSTGRES_HOST') == 'postgres' else os.getenv('POSTGRES_HOST', 'localhost')
        conn_params = {
            'host': host,
            'port': int(os.getenv('POSTGRES_PORT', '5432')),
            'database': os.getenv('POSTGRES_DB', 'kosmos_db'),
            'user': os.getenv('POSTGRES_USER', 'kosmos_user'),
            'password': os.getenv('POSTGRES_PASSWORD', 'kosmos_password')
        }
        
        print(f"正在连接PostgreSQL: {conn_params['host']}:{conn_params['port']}/{conn_params['database']}")
        
        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # 测试连接
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        
        # 检查数据库是否存在表
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public';
        """)
        tables = cursor.fetchall()
        
        conn.close()
        
        return True, f"PostgreSQL连接成功 - 版本: {version['version']}, 表数量: {len(tables)}"
        
    except Exception as e:
        return False, f"PostgreSQL连接失败: {str(e)}"

def test_milvus_connection() -> Tuple[bool, str]:
    """测试Milvus连接"""
    try:
        # 在宿主机上运行时，使用localhost而不是服务名
        host = 'localhost' if os.getenv('MILVUS_HOST') == 'milvus' else os.getenv('MILVUS_HOST', 'localhost')
        port = os.getenv('MILVUS_PORT', '19530')
        
        print(f"正在连接Milvus: {host}:{port}")
        
        token = os.getenv('MILVUS_TOKEN')
        if token:
            # 解析token格式: user:password
            user, password = token.split(':')
            connections.connect(
                alias="default",
                host=host,
                port=port,
                user=user,
                password=password
            )
        else:
            # 官方安装方式，使用默认凭证 root:Milvus
            connections.connect(
                alias="default",
                host=host,
                port=port,
                user='root',
                password='Milvus'
            )
        
        # 测试连接
        status = utility.get_server_version()
        
        # 获取集合列表
        collections = utility.list_collections()
        
        connections.disconnect("default")
        
        return True, f"Milvus连接成功 - 版本: {status}, 集合数量: {len(collections)}"
        
    except Exception as e:
        return False, f"Milvus连接失败: {str(e)}"

def wait_for_services(max_retries: int = 30, retry_interval: int = 2):
    """等待服务启动"""
    print("等待服务启动...")
    
    for i in range(max_retries):
        pg_success, pg_msg = test_postgresql_connection()
        mv_success, mv_msg = test_milvus_connection()
        
        if pg_success and mv_success:
            print("✓ 所有服务已就绪")
            return True
        
        print(f"重试 {i+1}/{max_retries}: PostgreSQL: {'✓' if pg_success else '✗'}, Milvus: {'✓' if mv_success else '✗'}")
        time.sleep(retry_interval)
    
    return False

def main():
    """主函数"""
    print("=" * 50)
    print("Kosmos 数据库连接测试工具")
    print("=" * 50)
    
    # 加载环境变量
    load_environment()
    
    # 打印环境变量配置（隐藏密码）
    print("\n环境变量配置:")
    print(f"  PostgreSQL Host: {os.getenv('POSTGRES_HOST')}")
    print(f"  PostgreSQL Port: {os.getenv('POSTGRES_PORT')}")
    print(f"  PostgreSQL User: {os.getenv('POSTGRES_USER')}")
    print(f"  PostgreSQL DB: {os.getenv('POSTGRES_DB')}")
    print(f"  Milvus Host: {os.getenv('MILVUS_HOST')}")
    print(f"  Milvus Port: {os.getenv('MILVUS_PORT')}")
    
    # 测试连接
    print("\n" + "=" * 30)
    print("开始测试连接...")
    
    # 直接测试连接
    pg_success, pg_msg = test_postgresql_connection()
    mv_success, mv_msg = test_milvus_connection()
    
    print(f"\nPostgreSQL: {pg_msg}")
    print(f"Milvus: {mv_msg}")
    
    # 如果连接失败，提供等待选项
    if not pg_success or not mv_success:
        print("\n" + "-" * 30)
        response = input("连接失败，是否等待服务启动？(y/n): ").strip().lower()
        if response == 'y':
            if wait_for_services():
                print("✓ 所有服务已正常连接")
            else:
                print("✗ 服务启动超时，请检查Docker容器状态")
                sys.exit(1)
    else:
        print("\n✓ 所有服务连接正常")

if __name__ == "__main__":
    main()