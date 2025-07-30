#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清空数据库所有表数据的脚本
创建时间: 2025-01-27
描述: 执行clear_all_tables.sql脚本来清空所有表数据
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.db.database import engine
from sqlalchemy import text

def clear_all_tables():
    """
    清空所有表数据
    """
    try:
        # 读取SQL脚本
        script_path = Path(__file__).parent / "clear_all_tables.sql"
        with open(script_path, 'r', encoding='utf-8') as f:
            sql_script = f.read()
        
        print("开始清空数据库表...")
        
        # 执行SQL脚本
        with engine.connect() as connection:
            # 分割SQL语句并逐个执行
            statements = [stmt.strip() for stmt in sql_script.split(';') if stmt.strip()]
            
            for statement in statements:
                if statement and not statement.startswith('--'):
                    print(f"执行: {statement[:50]}...")
                    connection.execute(text(statement))
            
            connection.commit()
        
        print("✅ 数据库表清空完成！")
        
    except Exception as e:
        print(f"❌ 清空数据库表时发生错误: {e}")
        raise

def main():
    """
    主函数
    """
    print("Kosmos数据库清空工具")
    print("=" * 50)
    
    # 确认操作
    confirm = input("⚠️  警告: 此操作将清空所有表数据，无法恢复！是否继续？(yes/no): ")
    if confirm.lower() != 'yes':
        print("操作已取消。")
        return
    
    try:
        clear_all_tables()
        print("\n🎉 数据库清空操作完成！")
    except Exception as e:
        print(f"\n💥 操作失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()