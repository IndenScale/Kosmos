#!/bin/bash

# Kosmos Docker迁移脚本
# 用于将Kosmos从nohup管理迁移到Docker容器

echo "Kosmos Docker迁移脚本"
echo "======================"

# 停止所有当前的nohup服务
echo "停止当前nohup服务..."
./kosmos_service.sh stop

# 删除旧的容器
echo "删除旧的容器..."
docker stop kosmos-postgres 2>/dev/null || true
docker rm kosmos-postgres 2>/dev/null || true
docker stop kosmos-redis 2>/dev/null || true
docker rm kosmos-redis 2>/dev/null || true

# 启动新的容器
echo "启动新的Docker容器..."
docker compose -f docker-compose-final.yml up -d

echo "迁移完成！"
echo "请检查容器状态："
echo "docker ps"