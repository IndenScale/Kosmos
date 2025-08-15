@echo off
REM Kosmos v2.0 启动脚本 (批处理版本)
REM 简化的Windows启动方式

echo.
echo ========================================
echo    Kosmos v2.0 知识库系统启动器
echo ========================================
echo.

REM 检查PowerShell是否可用
powershell -Command "Get-Host" >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 需要PowerShell支持
    echo 请确保系统已安装PowerShell
    pause
    exit /b 1
)

REM 获取脚本目录
set SCRIPT_DIR=%~dp0

REM 检查PowerShell脚本是否存在
if not exist "%SCRIPT_DIR%start_kosmos_v2.ps1" (
    echo 错误: 找不到PowerShell启动脚本
    echo 请确保 start_kosmos_v2.ps1 文件存在
    pause
    exit /b 1
)

REM 显示菜单
echo 请选择启动模式:
echo 1. 启动完整系统 (前端 + 后端)
echo 2. 仅启动后端
echo 3. 仅启动前端
echo 4. 查看服务状态
echo 5. 停止所有服务
echo 0. 退出
echo.
set /p choice=请输入选择 (0-5): 

if "%choice%"=="1" (
    echo 启动完整系统...
    powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%start_kosmos_v2.ps1" -Mode all
) else if "%choice%"=="2" (
    echo 启动后端服务...
    powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%start_kosmos_v2.ps1" -Mode backend
) else if "%choice%"=="3" (
    echo 启动前端服务...
    powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%start_kosmos_v2.ps1" -Mode frontend
) else if "%choice%"=="4" (
    echo 查看服务状态...
    powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%start_kosmos_v2.ps1" -Status
) else if "%choice%"=="5" (
    echo 停止所有服务...
    powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%start_kosmos_v2.ps1" -Stop
) else if "%choice%"=="0" (
    echo 退出...
    exit /b 0
) else (
    echo 无效选择，请重新运行脚本
)

echo.
pause