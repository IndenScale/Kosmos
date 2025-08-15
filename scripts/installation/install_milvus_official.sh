#!/bin/bash

# Milvus官方独立安装脚本
# 使用官方推荐的安装方式

set -e

echo "开始安装Milvus（官方独立模式）..."

# 创建milvus目录
mkdir -p /home/hxdi/AssessmentSystem/Kosmos/volumes/milvus_official

# 下载官方安装脚本
echo "下载Milvus官方安装脚本..."
curl -sfL https://raw.githubusercontent.com/milvus-io/milvus/master/scripts/standalone_embed.sh -o standalone_embed.sh

# 添加执行权限
chmod +x standalone_embed.sh

# 启动Milvus容器
echo "启动Milvus容器..."
bash standalone_embed.sh start

# 等待服务启动
echo "等待Milvus服务启动..."
sleep 10

# 检查服务状态
echo "检查Milvus服务状态..."
docker ps | grep milvus

echo "Milvus安装完成！"
echo "访问地址: http://localhost:19530"
echo "默认用户名: root"
echo "默认密码: Milvus"

# 创建.env文件更新
echo "更新环境变量配置..."
cat >> /home/hxdi/AssessmentSystem/Kosmos/.env << EOF

# Milvus官方安装配置
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_TOKEN=root:Milvus
EOF

echo "配置已更新到.env文件"