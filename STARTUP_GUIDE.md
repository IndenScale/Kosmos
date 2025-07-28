# Kosmos v2.0 启动指南

Kosmos v2.0 提供了标准化的启动脚本，支持跨平台的统一启动方式。

## 快速启动

### Windows 用户

#### 方式一：使用批处理文件（推荐）
```cmd
# 双击运行或在命令行执行
start_kosmos_v2.bat
```

#### 方式二：使用PowerShell脚本
```powershell
# 启动完整系统
.\start_kosmos_v2.ps1

# 仅启动后端
.\start_kosmos_v2.ps1 -Mode backend

# 仅启动前端
.\start_kosmos_v2.ps1 -Mode frontend

# 查看服务状态
.\start_kosmos_v2.ps1 -Status

# 停止所有服务
.\start_kosmos_v2.ps1 -Stop
```

### Linux/macOS 用户

```bash
# 启动完整系统
./start_kosmos.sh

# 仅启动后端
./start_kosmos.sh backend

# 仅启动前端
./start_kosmos.sh frontend

# 查看服务状态
./start_kosmos.sh status

# 停止所有服务
./start_kosmos.sh stop

# 显示帮助
./start_kosmos.sh help
```

## 服务地址

启动成功后，可以通过以下地址访问服务：

- **前端界面**: http://localhost:3000
- **后端API**: http://localhost:8000
- **API文档**: http://localhost:8000/docs

## 日志和进程管理

### 日志文件位置
- 后端日志: `logs/backend.log`
- 前端日志: `logs/frontend.log`

### 进程ID文件
- 后端PID: `pids/backend.pid`
- 前端PID: `pids/frontend.pid`

## 故障排除

### 1. 端口占用问题
如果遇到端口占用，可以：
- 使用 `./start_kosmos.sh status` 查看当前服务状态
- 使用 `./start_kosmos.sh stop` 停止现有服务
- 检查其他程序是否占用了3000或8000端口

### 2. 前端依赖问题
如果前端启动失败，可能是依赖未安装：
```bash
cd frontend
npm install
```

### 3. 后端依赖问题
确保已安装Python依赖：
```bash
pip install -r requirements.txt
```

### 4. 权限问题（Linux/macOS）
如果脚本无法执行，需要添加执行权限：
```bash
chmod +x start_kosmos.sh
chmod +x scripts/start.bash
```

## 开发模式

对于开发者，可以分别启动前端和后端：

### 启动后端（开发模式）
```bash
# Linux/macOS
./start_kosmos.sh backend

# Windows
.\start_kosmos_v2.ps1 -Mode backend
```

### 启动前端（开发模式）
```bash
# Linux/macOS
./start_kosmos.sh frontend

# Windows
.\start_kosmos_v2.ps1 -Mode frontend
```

## 版本升级说明

### 从v1.x升级到v2.0

1. **新的启动方式**: 使用新的标准化启动脚本
2. **日志管理**: 日志文件统一存放在 `logs/` 目录
3. **进程管理**: PID文件统一存放在 `pids/` 目录
4. **服务管理**: 支持独立启动/停止前端和后端
5. **状态监控**: 新增服务状态查看功能

### 兼容性说明

- 旧的启动脚本仍然可用，但建议使用新的标准化脚本
- 服务端口保持不变（前端3000，后端8000）
- API接口保持向后兼容

## 技术支持

如果遇到问题，请：
1. 查看日志文件获取详细错误信息
2. 确认系统环境满足要求
3. 检查网络和防火墙设置
4. 提交Issue到项目仓库