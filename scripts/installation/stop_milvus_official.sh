#!/bin/bash

# 停止Milvus官方安装

set -e

echo "停止Milvus官方容器..."

# 检查是否存在standalone_embed.sh
if [ -f "standalone_embed.sh" ]; then
    bash standalone_embed.sh stop
    echo "Milvus容器已停止"
else
    echo "未找到standalone_embed.sh，尝试手动停止容器..."
    
    # 停止可能存在的milvus容器
    docker stop milvus-standalone 2>/dev/null || true
    docker rm milvus-standalone 2>/dev/null || true
    
    echo "Milvus容器已手动停止"
fi