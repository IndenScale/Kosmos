#!/usr/bin/env python3
"""
Kosmos MCP Server启动脚本
"""

import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server import main

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())