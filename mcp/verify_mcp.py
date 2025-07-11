#!/usr/bin/env python3
"""
验证MCP服务器设置的脚本
"""

import sys
import os

def check_imports():
    """检查必要的导入"""
    print("🔍 检查导入...")
    try:
        from mcp.server import Server
        from mcp.types import Tool, Resource, TextContent
        print("✅ MCP模块导入成功")
        return True
    except ImportError as e:
        print(f"❌ MCP模块导入失败: {e}")
        return False

def check_server_definition():
    """检查服务器定义"""
    print("🔍 检查服务器定义...")
    try:
        from server import server, handle_list_tools, handle_list_resources, handle_call_tool
        print("✅ 服务器和处理函数定义正确")
        return True
    except ImportError as e:
        print(f"❌ 服务器定义有问题: {e}")
        return False

def check_config():
    """检查配置"""
    print("🔍 检查配置...")
    from dotenv import load_dotenv
    load_dotenv()
    
    base_url = os.getenv('KOSMOS_BASE_URL')
    username = os.getenv('KOSMOS_USERNAME')
    password = os.getenv('KOSMOS_PASSWORD')
    
    if base_url and username and password:
        print("✅ 配置文件正确")
        return True
    else:
        print("❌ 配置文件缺少必要信息")
        return False

def main():
    """主函数"""
    print("🧪 验证MCP服务器设置...\n")
    
    checks = [
        check_imports,
        check_config,
        check_server_definition
    ]
    
    all_passed = True
    for check in checks:
        try:
            if not check():
                all_passed = False
        except Exception as e:
            print(f"❌ 检查过程中出错: {e}")
            all_passed = False
        print()
    
    if all_passed:
        print("🎉 所有检查通过！MCP服务器应该可以正常工作。")
        print("💡 如果仍然显示0个工具，请尝试:")
        print("  1. 重启MCP客户端")
        print("  2. 检查配置文件路径是否正确")
        print("  3. 查看客户端日志")
    else:
        print("💥 有检查失败，请修复后再试。")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)