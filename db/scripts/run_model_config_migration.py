#!/usr/bin/env python3
"""
模型配置重构主迁移脚本
文件: run_model_config_migration.py
创建时间: 2025-07-26
描述: 协调执行模型配置重构的完整迁移流程
"""

import os
import sys
import subprocess
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 数据库连接配置
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "kosmos")

SQLALCHEMY_DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

def execute_sql_file(file_path, description):
    """执行SQL文件"""
    print(f"\n{'='*60}")
    print(f"执行: {description}")
    print(f"文件: {file_path}")
    print(f"{'='*60}")

    if not os.path.exists(file_path):
        print(f"❌ 错误: 文件 {file_path} 不存在")
        return False

    try:
        engine = create_engine(SQLALCHEMY_DATABASE_URL)

        with open(file_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        # 分割SQL语句（简单处理，按分号分割）
        sql_statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]

        with engine.connect() as conn:
            for stmt in sql_statements:
                if stmt.upper().startswith('PRINT'):
                    # 处理PRINT语句
                    message = stmt.replace('PRINT', '').strip().strip("'\"")
                    print(f"📢 {message}")
                elif stmt.strip():
                    try:
                        conn.execute(text(stmt))
                        conn.commit()
                    except Exception as e:
                        print(f"⚠️ SQL语句执行警告: {e}")
                        print(f"语句: {stmt[:100]}...")

        print(f"✅ {description} 执行完成")
        return True

    except Exception as e:
        print(f"❌ 执行 {description} 时发生错误: {e}")
        return False

def execute_python_script(script_path, description):
    """执行Python脚本"""
    print(f"\n{'='*60}")
    print(f"执行: {description}")
    print(f"脚本: {script_path}")
    print(f"{'='*60}")

    if not os.path.exists(script_path):
        print(f"❌ 错误: 脚本 {script_path} 不存在")
        return False

    try:
        # 使用当前Python解释器执行脚本
        result = subprocess.run([sys.executable, script_path],
                              capture_output=True,
                              text=True,
                              cwd=os.path.dirname(script_path))

        if result.stdout:
            print("📤 输出:")
            print(result.stdout)

        if result.stderr:
            print("⚠️ 错误输出:")
            print(result.stderr)

        if result.returncode == 0:
            print(f"✅ {description} 执行完成")
            return True
        else:
            print(f"❌ {description} 执行失败，返回码: {result.returncode}")
            return False

    except Exception as e:
        print(f"❌ 执行 {description} 时发生错误: {e}")
        return False

def check_prerequisites():
    """检查迁移前提条件"""
    print("🔍 检查迁移前提条件...")

    try:
        engine = create_engine(SQLALCHEMY_DATABASE_URL)
        with engine.connect() as conn:
            # 检查数据库连接
            conn.execute(text("SELECT 1"))
            print("✅ 数据库连接正常")

            # 检查必要的表是否存在
            tables_to_check = ['users', 'knowledge_bases']
            for table in tables_to_check:
                result = conn.execute(text(f"""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = '{table}'
                    )
                """)).scalar()

                if result:
                    print(f"✅ 表 {table} 存在")
                else:
                    print(f"❌ 表 {table} 不存在")
                    return False

            return True

    except Exception as e:
        print(f"❌ 前提条件检查失败: {e}")
        return False

def main():
    """主迁移流程"""
    print("🚀 Kosmos 模型配置重构迁移")
    print("=" * 80)
    print("此脚本将执行以下步骤:")
    print("1. 检查迁移前提条件")
    print("2. 创建新的模型配置表")
    print("3. 迁移现有数据")
    print("4. 验证迁移结果")
    print("5. (可选) 删除旧字段")
    print("=" * 80)

    # 获取脚本目录
    script_dir = Path(__file__).parent

    # 定义文件路径
    create_tables_sql = script_dir / "create_model_credential_tables.sql"
    migrate_data_py = script_dir / "migrate_model_configs.py"
    drop_old_fields_sql = script_dir / "drop_old_embedding_config.sql"

    try:
        # 步骤1: 检查前提条件
        if not check_prerequisites():
            print("❌ 前提条件检查失败，迁移终止")
            return False

        # 步骤2: 创建新表
        if not execute_sql_file(create_tables_sql, "创建模型配置表"):
            print("❌ 创建表失败，迁移终止")
            return False

        # 步骤3: 迁移数据
        if not execute_python_script(migrate_data_py, "迁移现有数据"):
            print("❌ 数据迁移失败，迁移终止")
            return False

        # 步骤4: 询问是否删除旧字段
        print("\n" + "="*60)
        print("🤔 数据迁移完成！")
        print("是否要删除旧的 embedding_config 字段？")
        print("⚠️  警告: 这是不可逆操作！")
        print("建议先验证新系统运行正常后再执行此步骤。")

        user_input = input("输入 'yes' 确认删除旧字段，或按回车跳过: ").strip().lower()

        if user_input == 'yes':
            if execute_sql_file(drop_old_fields_sql, "删除旧字段"):
                print("✅ 旧字段删除完成")
            else:
                print("❌ 删除旧字段失败")
                return False
        else:
            print("⏭️  跳过删除旧字段，可以稍后手动执行")

        print("\n" + "🎉" * 20)
        print("🎉 模型配置重构迁移完成！")
        print("🎉" * 20)
        print("\n下一步:")
        print("1. 更新应用代码以使用新的模型配置表")
        print("2. 测试新的凭证管理功能")
        print("3. 如果一切正常，可以删除备份数据")

        return True

    except KeyboardInterrupt:
        print("\n❌ 用户中断迁移")
        return False
    except Exception as e:
        print(f"\n❌ 迁移过程中发生未预期错误: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)