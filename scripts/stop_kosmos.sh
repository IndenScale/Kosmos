#!/bin/bash

# Kosmos 知识库系统停止脚本
# 停止所有相关服务

set -e

# 颜色输出函数
red() { echo -e "\033[31m$1\033[0m"; }
green() { echo -e "\033[32m$1\033[0m"; }
yellow() { echo -e "\033[33m$1\033[0m"; }

echo "=========================================="
echo "      Kosmos 知识库系统停止脚本"
echo "=========================================="

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 停止后端服务
echo "正在停止Kosmos后端服务..."
if pgrep -f "uvicorn.*app.main:app" > /dev/null; then
    pkill -f "uvicorn.*app.main:app"
    green "Kosmos后端服务已停止"
else
    yellow "Kosmos后端服务未运行"
fi

# 停止前端服务
echo "正在停止Kosmos前端服务..."
if pgrep -f "npm.*start" > /dev/null; then
    pkill -f "npm.*start"
    green "Kosmos前端服务已停止"
else
    yellow "Kosmos前端服务未运行"
fi

# 停止Milvus服务
echo "正在停止Milvus服务..."
if [ -f "standalone_embed.sh" ]; then
    bash standalone_embed.sh stop
    green "Milvus服务已停止"
elif docker ps -q -f name=milvus-standalone | grep -q .; then
    docker stop milvus-standalone
    green "Milvus服务已停止"
else
    yellow "Milvus服务未运行"
fi

# 停止PostgreSQL服务
echo "正在停止PostgreSQL服务..."
if [ -f "docker-compose-lite.yml" ]; then
    docker compose -f docker-compose-lite.yml down
    green "PostgreSQL服务已停止"
elif [ -f "docker-compose.yml" ]; then
    docker compose down
    green "所有Docker服务已停止"
else
    yellow "PostgreSQL服务未运行"
fi

echo "=========================================="
green "      Kosmos 知识库系统已完全停止！"
echo "=========================================="