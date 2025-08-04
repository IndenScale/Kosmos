#!/bin/bash

# Frontend后台启动脚本
# 读取.env文件中的配置并后台启动React前端，输出日志到文件

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
LOGS_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOGS_DIR/frontend.log"

# 创建logs目录
mkdir -p "$LOGS_DIR"

# 检查.env文件是否存在
if [ ! -f "$ENV_FILE" ]; then
    echo "错误: .env文件不存在于 $ENV_FILE" | tee -a "$LOG_FILE"
    exit 1
fi

# 检查frontend目录是否存在
if [ ! -d "$FRONTEND_DIR" ]; then
    echo "错误: frontend目录不存在于 $FRONTEND_DIR" | tee -a "$LOG_FILE"
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

# 记录启动信息
echo "$(date): 启动前端服务..." >> "$LOG_FILE"
echo "$(date): KOSMOS_WEBUI_HOST: $KOSMOS_WEBUI_HOST" >> "$LOG_FILE"
echo "$(date): KOSMOS_WEBUI_PORT: $KOSMOS_WEBUI_PORT" >> "$LOG_FILE"
echo "$(date): KOSMOS_SERVER_HOST: $KOSMOS_SERVER_HOST" >> "$LOG_FILE"
echo "$(date): KOSMOS_SERVER_PORT: $KOSMOS_SERVER_PORT" >> "$LOG_FILE"

# 设置环境变量
export PORT=$KOSMOS_WEBUI_PORT
export HOST=$KOSMOS_WEBUI_HOST
export REACT_APP_API_BASE_URL="http://$KOSMOS_SERVER_HOST:$KOSMOS_SERVER_PORT"

# 进入frontend目录
cd "$FRONTEND_DIR"

# 检查是否已安装依赖
if [ ! -d "node_modules" ]; then
    echo "$(date): 正在安装依赖..." >> "$LOG_FILE"
    npm install >> "$LOG_FILE" 2>&1
fi

# 启动React应用，后台运行
export NODE_OPTIONS="--max-old-space-size=4096"
export BROWSER=none

echo "$(date): 正在启动前端服务..." >> "$LOG_FILE"
echo "$(date): 服务将在 http://$KOSMOS_WEBUI_HOST:$KOSMOS_WEBUI_PORT 启动" >> "$LOG_FILE"

# 使用nohup后台启动，输出重定向到日志文件
nohup npm start >> "$LOG_FILE" 2>&1 &

# 获取进程ID
FRONTEND_PID=$!
echo "$(date): 前端服务已启动，进程ID: $FRONTEND_PID" >> "$LOG_FILE"
echo "前端服务已启动，进程ID: $FRONTEND_PID"
echo "日志文件: $LOG_FILE"
echo "使用 'tail -f $LOG_FILE' 查看实时日志"