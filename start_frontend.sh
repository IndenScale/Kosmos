#!/bin/bash

# Frontend启动脚本
# 读取.env文件中的配置并启动React前端

set -e

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

# 检查.env文件是否存在
if [ ! -f "$ENV_FILE" ]; then
    echo "错误: .env文件不存在于 $ENV_FILE"
    exit 1
fi

# 检查frontend目录是否存在
if [ ! -d "$FRONTEND_DIR" ]; then
    echo "错误: frontend目录不存在于 $FRONTEND_DIR"
    exit 1
fi

# 从.env文件中读取配置
KOSMOS_WEBUI_HOST=$(grep "^KOSMOS_WEBUI_HOST=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' | tr -d '\r')
KOSMOS_WEBUI_PORT=$(grep "^KOSMOS_WEBUI_PORT=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' | tr -d '\r')
KOSMOS_SERVER_HOST=$(grep "^KOSMOS_SERVER_HOST=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' | tr -d '\r')
KOSMOS_SERVER_PORT=$(grep "^KOSMOS_SERVER_PORT=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' | tr -d '\r')

# 如果找不到配置，使用默认值
if [ -z "$KOSMOS_WEBUI_HOST" ]; then
    KOSMOS_WEBUI_HOST="localhost"
fi

if [ -z "$KOSMOS_WEBUI_PORT" ]; then
    KOSMOS_WEBUI_PORT="3020"
fi

if [ -z "$KOSMOS_SERVER_HOST" ]; then
    KOSMOS_SERVER_HOST="localhost"
fi

if [ -z "$KOSMOS_SERVER_PORT" ]; then
    KOSMOS_SERVER_PORT="8020"
fi

echo "读取配置:"
echo "  KOSMOS_WEBUI_HOST: $KOSMOS_WEBUI_HOST"
echo "  KOSMOS_WEBUI_PORT: $KOSMOS_WEBUI_PORT"
echo "  KOSMOS_SERVER_HOST: $KOSMOS_SERVER_HOST"
echo "  KOSMOS_SERVER_PORT: $KOSMOS_SERVER_PORT"

# 设置环境变量
export PORT=$KOSMOS_WEBUI_PORT
export HOST=$KOSMOS_WEBUI_HOST
export REACT_APP_API_BASE_URL="http://$KOSMOS_SERVER_HOST:$KOSMOS_SERVER_PORT"

# 进入frontend目录
cd "$FRONTEND_DIR"

# 检查是否已安装依赖
if [ ! -d "node_modules" ]; then
    echo "正在安装依赖..."
    npm install
fi

echo "正在启动前端服务..."
echo "服务将在 http://$KOSMOS_WEBUI_HOST:$KOSMOS_WEBUI_PORT 启动"

# 启动React应用
export NODE_OPTIONS="--max-old-space-size=4096"
export BROWSER=none

# 使用React Scripts启动应用
npm start