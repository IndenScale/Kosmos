# 系统部署运维备忘录

## 概述

本文档记录了系统部署和运维的关键信息，包括服务架构、部署配置和运维指南。

## 系统架构

系统采用事件驱动架构，包含以下核心组件：

1. **后端服务** - 提供API接口
2. **事件中继器** - 从后端领域事件表中拉取事件并发布到消息队列
3. **消息队列 (Redis)** - 用于服务间通信
4. **服务层** - 包括内容提取、资产分析、Chunking、Indexing等服务

## 服务依赖关系

- 内容提取 → 资产分析
- 内容提取 → Chunking
- Chunking → Indexing

## 部署配置

### 服务解耦与单实例部署

为提高系统稳定性，已将统一的Dramatiq worker服务分解为独立的worker服务：

- `dramatiq_content_extraction_worker`
- `dramatiq_asset_analysis_worker`
- `dramatiq_chunking_worker`
- `dramatiq_indexing_worker`

### 单实例部署配置

所有服务均配置为单实例部署模式，以实现更好的资源控制和稳定性。

### 资产分析服务特殊配置

由于VLM推理资源是瓶颈，资产分析服务配置为单进程单线程模式，以避免资源竞争。

## 运维指南

### 启动服务

```bash
# 启动特定服务
./kosmos_service.sh start dramatiq_content_extraction_worker

# 启动所有服务
./kosmos_service.sh start
```

### 停止服务

```bash
# 停止特定服务
./kosmos_service.sh stop dramatiq_asset_analysis_worker

# 停止所有服务
./kosmos_service.sh stop
```

### 查看服务状态

```bash
# 查看特定服务状态
./kosmos_service.sh status dramatiq_chunking_worker

# 查看所有服务状态
./kosmos_service.sh status
```

### 清空消息队列

```bash
# 清空所有Dramatiq消息队列
./kosmos_service.sh clear-queues
```

### 重启服务

由于启动脚本的修改不会被uvicorn的reload功能检测到，当您修改了启动脚本后，需要手动重启相关服务：

```bash
# 重启特定服务
./kosmos_service.sh restart api_server
./kosmos_service.sh restart assessment_server

# 或者分别重启
./kosmos_service.sh stop api_server
./kosmos_service.sh start api_server
./kosmos_service.sh stop assessment_server
./kosmos_service.sh start assessment_server
```

## 注意事项

1. 所有服务脚本都已设置执行权限
2. 资产分析服务已配置为单进程单线程模式
3. 每个服务可以独立管理、重启和扩容
4. 系统现在支持流水线并行处理

## 故障排除

如果遇到服务启动问题，请检查以下内容：

1. 确保所有脚本都有执行权限
2. 检查Redis服务是否正常运行
3. 确认环境变量配置正确
4. 查看对应服务的日志文件以获取详细错误信息