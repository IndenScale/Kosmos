# Kosmos v2.0 标准化启动脚本 (PowerShell)
# 支持前端和后端的统一启动管理

param(
    [string]$Mode = "all",  # all, frontend, backend
    [switch]$Dev = $false,  # 开发模式
    [switch]$Stop = $false, # 停止服务
    [switch]$Status = $false # 查看状态
)

# 配置
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$BACKEND_DIR = $SCRIPT_DIR
$FRONTEND_DIR = Join-Path $SCRIPT_DIR "frontend"
$LOG_DIR = Join-Path $SCRIPT_DIR "logs"
$PID_DIR = Join-Path $SCRIPT_DIR "pids"

# 创建必要的目录
if (!(Test-Path $LOG_DIR)) { New-Item -ItemType Directory -Path $LOG_DIR -Force | Out-Null }
if (!(Test-Path $PID_DIR)) { New-Item -ItemType Directory -Path $PID_DIR -Force | Out-Null }

# 日志和PID文件路径
$BACKEND_LOG = Join-Path $LOG_DIR "backend.log"
$FRONTEND_LOG = Join-Path $LOG_DIR "frontend.log"
$BACKEND_PID = Join-Path $PID_DIR "backend.pid"
$FRONTEND_PID = Join-Path $PID_DIR "frontend.pid"

# 颜色输出函数
function Write-ColorOutput {
    param([string]$Message, [string]$Color = "White")
    Write-Host $Message -ForegroundColor $Color
}

# 检查进程是否运行
function Test-ProcessRunning {
    param([string]$PidFile)
    if (Test-Path $PidFile) {
        $pid = Get-Content $PidFile -ErrorAction SilentlyContinue
        if ($pid -and (Get-Process -Id $pid -ErrorAction SilentlyContinue)) {
            return $true
        }
    }
    return $false
}

# 停止进程
function Stop-ServiceProcess {
    param([string]$PidFile, [string]$ServiceName)
    if (Test-Path $PidFile) {
        $pid = Get-Content $PidFile -ErrorAction SilentlyContinue
        if ($pid) {
            try {
                Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
                Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
                Write-ColorOutput "✓ $ServiceName 已停止" "Green"
            } catch {
                Write-ColorOutput "✗ 停止 $ServiceName 失败: $_" "Red"
            }
        }
    }
}

# 启动后端
function Start-Backend {
    Write-ColorOutput "🚀 启动 Kosmos v2.0 后端服务..." "Cyan"
    
    # 检查是否已经运行
    if (Test-ProcessRunning $BACKEND_PID) {
        Write-ColorOutput "⚠️  后端服务已在运行中" "Yellow"
        return
    }
    
    # 切换到后端目录
    Push-Location $BACKEND_DIR
    
    try {
        # 启动后端服务
        $process = Start-Process -FilePath "uvicorn" -ArgumentList @(
            "app.main:app",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--timeout-keep-alive", "600",
            "--log-level", "info"
        ) -PassThru -RedirectStandardOutput $BACKEND_LOG -RedirectStandardError $BACKEND_LOG -WindowStyle Hidden
        
        # 保存PID
        $process.Id | Out-File -FilePath $BACKEND_PID -Encoding utf8
        
        Write-ColorOutput "✓ 后端服务已启动 (PID: $($process.Id))" "Green"
        Write-ColorOutput "  - 服务地址: http://localhost:8000" "Gray"
        Write-ColorOutput "  - API文档: http://localhost:8000/docs" "Gray"
        Write-ColorOutput "  - 日志文件: $BACKEND_LOG" "Gray"
    } catch {
        Write-ColorOutput "✗ 后端启动失败: $_" "Red"
    } finally {
        Pop-Location
    }
}

# 启动前端
function Start-Frontend {
    Write-ColorOutput "🎨 启动 Kosmos v2.0 前端服务..." "Cyan"
    
    # 检查是否已经运行
    if (Test-ProcessRunning $FRONTEND_PID) {
        Write-ColorOutput "⚠️  前端服务已在运行中" "Yellow"
        return
    }
    
    # 检查前端目录
    if (!(Test-Path $FRONTEND_DIR)) {
        Write-ColorOutput "✗ 前端目录不存在: $FRONTEND_DIR" "Red"
        return
    }
    
    # 切换到前端目录
    Push-Location $FRONTEND_DIR
    
    try {
        # 检查依赖
        if (!(Test-Path "node_modules")) {
            Write-ColorOutput "📦 安装前端依赖..." "Yellow"
            npm install
        }
        
        # 启动前端服务
        $process = Start-Process -FilePath "npm" -ArgumentList "start" -PassThru -RedirectStandardOutput $FRONTEND_LOG -RedirectStandardError $FRONTEND_LOG -WindowStyle Hidden
        
        # 保存PID
        $process.Id | Out-File -FilePath $FRONTEND_PID -Encoding utf8
        
        Write-ColorOutput "✓ 前端服务已启动 (PID: $($process.Id))" "Green"
        Write-ColorOutput "  - 服务地址: http://localhost:3000" "Gray"
        Write-ColorOutput "  - 日志文件: $FRONTEND_LOG" "Gray"
    } catch {
        Write-ColorOutput "✗ 前端启动失败: $_" "Red"
    } finally {
        Pop-Location
    }
}

# 停止所有服务
function Stop-AllServices {
    Write-ColorOutput "🛑 停止 Kosmos v2.0 服务..." "Cyan"
    Stop-ServiceProcess $BACKEND_PID "后端服务"
    Stop-ServiceProcess $FRONTEND_PID "前端服务"
}

# 查看服务状态
function Show-Status {
    Write-ColorOutput "📊 Kosmos v2.0 服务状态" "Cyan"
    Write-ColorOutput "=" * 40 "Gray"
    
    # 后端状态
    if (Test-ProcessRunning $BACKEND_PID) {
        $pid = Get-Content $BACKEND_PID
        Write-ColorOutput "✓ 后端服务: 运行中 (PID: $pid)" "Green"
        Write-ColorOutput "  - 服务地址: http://localhost:8000" "Gray"
    } else {
        Write-ColorOutput "✗ 后端服务: 未运行" "Red"
    }
    
    # 前端状态
    if (Test-ProcessRunning $FRONTEND_PID) {
        $pid = Get-Content $FRONTEND_PID
        Write-ColorOutput "✓ 前端服务: 运行中 (PID: $pid)" "Green"
        Write-ColorOutput "  - 服务地址: http://localhost:3000" "Gray"
    } else {
        Write-ColorOutput "✗ 前端服务: 未运行" "Red"
    }
}

# 主执行逻辑
Write-ColorOutput "🌟 Kosmos v2.0 知识库系统" "Magenta"
Write-ColorOutput "=" * 40 "Gray"

if ($Stop) {
    Stop-AllServices
} elseif ($Status) {
    Show-Status
} else {
    switch ($Mode.ToLower()) {
        "backend" {
            Start-Backend
        }
        "frontend" {
            Start-Frontend
        }
        "all" {
            Start-Backend
            Start-Sleep -Seconds 3
            Start-Frontend
        }
        default {
            Write-ColorOutput "✗ 无效的模式: $Mode" "Red"
            Write-ColorOutput "可用模式: all, backend, frontend" "Yellow"
            exit 1
        }
    }
    
    if ($Mode -eq "all" -or $Mode -eq "frontend") {
        Write-ColorOutput "" "White"
        Write-ColorOutput "🎉 Kosmos v2.0 启动完成!" "Green"
        Write-ColorOutput "前端访问地址: http://localhost:3000" "Cyan"
        Write-ColorOutput "后端API地址: http://localhost:8000" "Cyan"
        Write-ColorOutput "API文档地址: http://localhost:8000/docs" "Cyan"
        Write-ColorOutput "" "White"
        Write-ColorOutput "使用 './start_kosmos_v2.ps1 -Stop' 停止服务" "Yellow"
        Write-ColorOutput "使用 './start_kosmos_v2.ps1 -Status' 查看状态" "Yellow"
    }
}