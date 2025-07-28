#!/bin/bash

# Kosmos v2.0 标准化启动脚本 (Linux/macOS)
# 支持前端和后端的统一启动管理

# 配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
LOG_DIR="$SCRIPT_DIR/logs"
PID_DIR="$SCRIPT_DIR/pids"

# 创建必要的目录
mkdir -p "$LOG_DIR" "$PID_DIR"

# 日志和PID文件路径
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"
BACKEND_PID="$PID_DIR/backend.pid"
FRONTEND_PID="$PID_DIR/frontend.pid"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
GRAY='\033[0;37m'
NC='\033[0m' # No Color

# 输出函数
print_color() {
    echo -e "${1}${2}${NC}"
}

# 检查进程是否运行
is_running() {
    local pid_file="$1"
    if [[ -f "$pid_file" ]]; then
        local pid=$(cat "$pid_file" 2>/dev/null)
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
    fi
    return 1
}

# 停止进程
stop_service() {
    local pid_file="$1"
    local service_name="$2"
    
    if [[ -f "$pid_file" ]]; then
        local pid=$(cat "$pid_file" 2>/dev/null)
        if [[ -n "$pid" ]]; then
            if kill "$pid" 2>/dev/null; then
                rm -f "$pid_file"
                print_color "$GREEN" "✓ $service_name 已停止"
            else
                print_color "$RED" "✗ 停止 $service_name 失败"
            fi
        fi
    fi
}

# 启动后端
start_backend() {
    print_color "$CYAN" "🚀 启动 Kosmos v2.0 后端服务..."
    
    # 检查是否已经运行
    if is_running "$BACKEND_PID"; then
        print_color "$YELLOW" "⚠️  后端服务已在运行中"
        return
    fi
    
    # 切换到后端目录
    cd "$BACKEND_DIR" || exit 1
    
    # 启动后端服务
    nohup uvicorn app.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --timeout-keep-alive 600 \
        --log-level info \
        > "$BACKEND_LOG" 2>&1 &
    
    local pid=$!
    echo "$pid" > "$BACKEND_PID"
    
    print_color "$GREEN" "✓ 后端服务已启动 (PID: $pid)"
    print_color "$GRAY" "  - 服务地址: http://localhost:8000"
    print_color "$GRAY" "  - API文档: http://localhost:8000/docs"
    print_color "$GRAY" "  - 日志文件: $BACKEND_LOG"
}

# 启动前端
start_frontend() {
    print_color "$CYAN" "🎨 启动 Kosmos v2.0 前端服务..."
    
    # 检查是否已经运行
    if is_running "$FRONTEND_PID"; then
        print_color "$YELLOW" "⚠️  前端服务已在运行中"
        return
    fi
    
    # 检查前端目录
    if [[ ! -d "$FRONTEND_DIR" ]]; then
        print_color "$RED" "✗ 前端目录不存在: $FRONTEND_DIR"
        return
    fi
    
    # 切换到前端目录
    cd "$FRONTEND_DIR" || exit 1
    
    # 检查依赖
    if [[ ! -d "node_modules" ]]; then
        print_color "$YELLOW" "📦 安装前端依赖..."
        npm install
    fi
    
    # 启动前端服务
    nohup npm start > "$FRONTEND_LOG" 2>&1 &
    local pid=$!
    echo "$pid" > "$FRONTEND_PID"
    
    print_color "$GREEN" "✓ 前端服务已启动 (PID: $pid)"
    print_color "$GRAY" "  - 服务地址: http://localhost:3000"
    print_color "$GRAY" "  - 日志文件: $FRONTEND_LOG"
}

# 停止所有服务
stop_all() {
    print_color "$CYAN" "🛑 停止 Kosmos v2.0 服务..."
    stop_service "$BACKEND_PID" "后端服务"
    stop_service "$FRONTEND_PID" "前端服务"
}

# 查看服务状态
show_status() {
    print_color "$CYAN" "📊 Kosmos v2.0 服务状态"
    print_color "$GRAY" "========================================"
    
    # 后端状态
    if is_running "$BACKEND_PID"; then
        local pid=$(cat "$BACKEND_PID")
        print_color "$GREEN" "✓ 后端服务: 运行中 (PID: $pid)"
        print_color "$GRAY" "  - 服务地址: http://localhost:8000"
    else
        print_color "$RED" "✗ 后端服务: 未运行"
    fi
    
    # 前端状态
    if is_running "$FRONTEND_PID"; then
        local pid=$(cat "$FRONTEND_PID")
        print_color "$GREEN" "✓ 前端服务: 运行中 (PID: $pid)"
        print_color "$GRAY" "  - 服务地址: http://localhost:3000"
    else
        print_color "$RED" "✗ 前端服务: 未运行"
    fi
}

# 显示帮助
show_help() {
    echo "Kosmos v2.0 启动脚本"
    echo ""
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  all        启动完整系统 (默认)"
    echo "  backend    仅启动后端"
    echo "  frontend   仅启动前端"
    echo "  stop       停止所有服务"
    echo "  status     查看服务状态"
    echo "  help       显示此帮助信息"
    echo ""
}

# 主执行逻辑
print_color "$MAGENTA" "🌟 Kosmos v2.0 知识库系统"
print_color "$GRAY" "========================================"

case "${1:-all}" in
    "backend")
        start_backend
        ;;
    "frontend")
        start_frontend
        ;;
    "stop")
        stop_all
        ;;
    "status")
        show_status
        ;;
    "help"|"-h"|"--help")
        show_help
        ;;
    "all"|"")
        start_backend
        sleep 3
        start_frontend
        echo ""
        print_color "$GREEN" "🎉 Kosmos v2.0 启动完成!"
        print_color "$CYAN" "前端访问地址: http://localhost:3000"
        print_color "$CYAN" "后端API地址: http://localhost:8000"
        print_color "$CYAN" "API文档地址: http://localhost:8000/docs"
        echo ""
        print_color "$YELLOW" "使用 '$0 stop' 停止服务"
        print_color "$YELLOW" "使用 '$0 status' 查看状态"
        ;;
    *)
        print_color "$RED" "✗ 无效的选项: $1"
        show_help
        exit 1
        ;;
esac
