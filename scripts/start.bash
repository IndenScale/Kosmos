#!/bin/bash

# Kosmos v2.0 启动脚本 (scripts版本)
# 与根目录的启动脚本保持一致

# 获取项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# 执行根目录的启动脚本
exec "$PROJECT_ROOT/start_kosmos.sh" "$@"