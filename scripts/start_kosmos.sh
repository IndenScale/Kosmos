#!/bin/bash

# Kosmos 知识库系统启动脚本
# 支持同时启动PostgreSQL、Milvus和后端服务

set -e

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 颜色输出函数
red() { echo -e "\033[31m$1\033[0m"; }
green() { echo -e "\033[32m$1\033[0m"; }
yellow() { echo -e "\033[33m$1\033[0m"; }

echo "=========================================="
echo "      Kosmos 知识库系统启动脚本"
echo "=========================================="

# 检查Docker是否运行
if ! docker info > /dev/null 2>&1; then
    red "错误：Docker未运行，请先启动Docker服务"
    exit 1
fi

# 启动依赖服务（PostgreSQL）
echo "正在启动依赖服务..."
cd "$SCRIPT_DIR"
if [ -f "docker-compose-lite.yml" ]; then
    docker compose -f docker-compose-lite.yml up -d postgres
    green "PostgreSQL服务已启动"
else
    yellow "警告：未找到docker-compose-lite.yml，跳过PostgreSQL启动"
fi

# 检查并启动Milvus（使用官方安装方式）
echo "检查Milvus服务..."
if docker ps -q -f name=milvus-standalone | grep -q .; then
    green "Milvus服务已在运行"
else
    echo "正在启动Milvus服务..."
    if [ -f "standalone_embed.sh" ]; then
        bash standalone_embed.sh start
        green "Milvus服务已启动"
    else
        yellow "警告：未找到standalone_embed.sh，请手动启动Milvus"
    fi
fi

# 等待服务启动
echo "等待服务启动..."
sleep 5

# 测试数据库连接
echo "测试数据库连接..."
python scripts/installation/db_connection.py --wait

# 启动后端服务
echo "正在启动Kosmos后端服务..."
if [ -f "scripts/start_backend_v2.bash" ]; then
    bash scripts/start_backend_v2.bash
    green "Kosmos后端服务已启动"
else
    red "错误：未找到start_backend_v2.bash脚本"
    exit 1
fi

# 启动前端服务
echo "正在启动Kosmos前端服务..."
if [ -f "start_frontend.sh" ]; then
    bash start_frontend.sh &
    green "Kosmos前端服务已启动"
else
    yellow "警告：未找到start_frontend.sh脚本"
fi

echo "=========================================="
green "      Kosmos 知识库系统启动完成！"
echo "=========================================="
echo "后端API地址: http://localhost:8020"
echo "前端界面地址: http://localhost:3020"
echo ""
echo "查看日志:"
echo "  tail -f logs/kosmos_backend.log"
echo "  docker logs milvus-standalone"
echo "=========================================="