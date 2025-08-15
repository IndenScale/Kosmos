#!/bin/bash

# 切换到项目目录
cd ~/AssessmentSystem/Kosmos

# 检查虚拟环境是否存在
if [ ! -f ".venv/bin/activate" ]; then
    echo "错误：虚拟环境未找到，请先运行 'python -m venv .venv' 创建虚拟环境"
    exit 1
fi

# 激活虚拟环境
source .venv/bin/activate

# 创建logs目录（如果不存在）
mkdir -p logs

# 启动后端服务，后台运行并将输出重定向到日志文件
# 使用--reload-exclude排除Docker卷目录以避免权限错误
nohup uvicorn app.main:app --host 0.0.0.0 --port 8020 --reload --reload-exclude volumes/ > ~/AssessmentSystem/Kosmos/logs/kosmos_backend.log 2>&1 &

# 输出启动信息
echo "Kosmos后端服务已启动"
echo "日志文件: ~/AssessmentSystem/Kosmos/logs/kosmos_backend.log"
echo "使用 'tail -f ~/AssessmentSystem/Kosmos/logs/kosmos_backend.log' 查看实时日志"