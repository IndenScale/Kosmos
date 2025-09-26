#!/usr/bin/env python
"""
数据库Schema查看工具

用于查看PostgreSQL数据库中的表结构和枚举类型
特别关注枚举类型的值是否匹配
"""

import argparse
import os
import sys
from typing import List, Dict, Any, Optional

import sqlalchemy
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine


def get_connection_string() -> str:
    """获取数据库连接字符串，优先从环境变量获取"""
    # 从环境变量获取
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        return db_url
    
    # 从docker-compose.yml中的配置构建
    postgres_user = os.environ.get("POSTGRES_USER", "kosmos")
    postgres_password = os.environ.get("POSTGRES_PASSWORD", "kosmos123")
    postgres_host = os.environ.get("POSTGRES_HOST", "localhost")
    postgres_port = os.environ.get("POSTGRES_PORT", "55432")
    postgres_db = os.environ.get("POSTGRES_DB", "kosmos")
    
    return f"postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{postgres_db}"


def connect_to_db() -> Engine:
    """连接到数据库"""
    connection_string = get_connection_string()
    print(f"连接到数据库: {connection_string}")
    return create_engine(connection_string)


def get_all_tables(engine: Engine) -> List[str]:
    """获取所有表名"""
    inspector = inspect(engine)
    return inspector.get_table_names()


def get_table_columns(engine: Engine, table_name: str) -> List[Dict[str, Any]]:
    """获取表的列信息"""
    inspector = inspect(engine)
    return inspector.get_columns(table_name)


def get_enum_types(engine: Engine) -> Dict[str, List[str]]:
    """获取所有枚举类型及其值"""
    query = text("""
    SELECT 
        t.typname AS enum_name,
        e.enumlabel AS enum_value
    FROM 
        pg_type t
    JOIN 
        pg_enum e ON t.oid = e.enumtypid
    JOIN 
        pg_catalog.pg_namespace n ON n.oid = t.typnamespace
    WHERE 
        n.nspname = 'public'
    ORDER BY 
        t.typname, e.enumsortorder;
    """)
    
    result = {}
    with engine.connect() as conn:
        for row in conn.execute(query):
            enum_name = row.enum_name
            enum_value = row.enum_value
            
            if enum_name not in result:
                result[enum_name] = []
            
            result[enum_name].append(enum_value)
    
    return result


def get_enum_type_details(engine: Engine, enum_name: str) -> Optional[List[str]]:
    """获取指定枚举类型的详细信息"""
    query = text("""
    SELECT 
        e.enumlabel AS enum_value
    FROM 
        pg_type t
    JOIN 
        pg_enum e ON t.oid = e.enumtypid
    JOIN 
        pg_catalog.pg_namespace n ON n.oid = t.typnamespace
    WHERE 
        n.nspname = 'public' AND
        t.typname = :enum_name
    ORDER BY 
        e.enumsortorder;
    """)
    
    values = []
    with engine.connect() as conn:
        for row in conn.execute(query, {"enum_name": enum_name}):
            values.append(row.enum_value)
    
    return values if values else None


def print_table_schema(engine: Engine, table_name: str) -> None:
    """打印表结构"""
    columns = get_table_columns(engine, table_name)
    
    print(f"\n表名: {table_name}")
    print("-" * 80)
    print(f"{'列名':<30} {'类型':<20} {'可空':<10} {'默认值':<20}")
    print("-" * 80)
    
    for column in columns:
        name = column["name"]
        col_type = str(column["type"])
        nullable = "YES" if column.get("nullable", True) else "NO"
        default = str(column.get("default", ""))
        
        print(f"{name:<30} {col_type:<20} {nullable:<10} {default:<20}")


def print_enum_types(enum_types: Dict[str, List[str]]) -> None:
    """打印所有枚举类型"""
    print("\n枚举类型:")
    print("-" * 80)
    
    for enum_name, values in enum_types.items():
        print(f"{enum_name}: {', '.join(values)}")


def main() -> None:
    """主函数"""
    parser = argparse.ArgumentParser(description="查看数据库Schema")
    parser.add_argument("--table", "-t", help="指定要查看的表名")
    parser.add_argument("--enum", "-e", help="指定要查看的枚举类型")
    parser.add_argument("--all-tables", "-a", action="store_true", help="查看所有表")
    parser.add_argument("--all-enums", "-E", action="store_true", help="查看所有枚举类型")
    
    args = parser.parse_args()
    
    try:
        engine = connect_to_db()
        
        # 如果没有指定任何参数，默认显示所有枚举类型
        if not (args.table or args.enum or args.all_tables or args.all_enums):
            args.all_enums = True
        
        if args.table:
            print_table_schema(engine, args.table)
        
        if args.all_tables:
            tables = get_all_tables(engine)
            print("\n所有表:")
            for table in tables:
                print_table_schema(engine, table)
        
        if args.enum:
            values = get_enum_type_details(engine, args.enum)
            if values:
                print(f"\n枚举类型 {args.enum}: {', '.join(values)}")
            else:
                print(f"\n找不到枚举类型: {args.enum}")
        
        if args.all_enums:
            enum_types = get_enum_types(engine)
            print_enum_types(enum_types)
            
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()