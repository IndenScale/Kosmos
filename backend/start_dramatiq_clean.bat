@echo off
title Kosmos Dramatiq Worker (Clean Start)

echo === Kosmos Dramatiq Worker 清理启动 ===
echo.

REM 设置工作目录
cd /d %~dp0

REM 激活虚拟环境
echo 激活虚拟环境...
call .venv\Scripts\activate

REM 清理Dramatiq队列
echo.
echo 正在清理Dramatiq消息队列...
python scripts\clear_dramatiq_queue.py
if %errorlevel% neq 0 (
    echo 队列清理失败，停止启动
    pause
    exit /b 1
)

echo.
echo 队列清理完成，正在启动Dramatiq Worker...
echo.

REM 启动Dramatiq worker
dramatiq backend.app.broker --watch backend/app --processes 1 --threads 1

echo.
echo Dramatiq Worker已停止
pause