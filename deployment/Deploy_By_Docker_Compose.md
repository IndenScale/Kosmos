# Kosmos 系统部署文档

## 系统架构概述

Kosmos 系统是一个网络安全评估系统，包含知识库子系统、评估管理子系统与智能体子系统。系统需要以下基础设施组件：

1. **Redis** - 用作消息队列
2. **PostgreSQL** - 用于关系型数据存储
3. **MinIO** - 用于对象存储（使用现有容器）

### Milvus 向量数据库（独立部署）
- **Milvus** - 向量数据库服务，包含以下内部组件：
  - **etcd** - 用于元数据管理
  - **MinIO** - 用于向量数据存储（内部专用）
  
> **注意**：Milvus作为独立服务部署在自己的网络环境中，与Kosmos基础设施组件分离。

## 网络规划

### Kosmos基础设施网络
我们将创建一个自定义的 Docker 网络以确保Kosmos核心组件间安全通信：

- 网络名称：`kosmos-network`
- 网络类型：内部网络（仅容器间通信）
- 驱动类型：bridge

### Milvus内部网络
Milvus服务使用自己的内部网络来连接其组件（etcd, MinIO, standalone）。

## 端口规划

### Kosmos基础设施外部端口映射（宿主机）
- Redis: 6379 -> 56379
- PostgreSQL: 5432 -> 55432
- MinIO: 9000-9001 -> 9000-9001（现有容器，非Kosmos专用）

### Milvus服务外部端口映射（宿主机）
- Milvus gRPC: 19530 -> 59530
- Milvus HTTP API / WebUI: 9091 -> 9092

> **注意**：Milvus内部组件（etcd和内部MinIO）不对外暴露端口，仅在Milvus内部网络中通信。

## 组件依赖关系

### Kosmos核心服务依赖
- 知识库后端依赖：PostgreSQL, Redis, Milvus, 外部MinIO
- 评估服务后端依赖：PostgreSQL, Redis
- 智能体子系统依赖：评估服务和知识库的API（不直接访问基础设施）

### Milvus内部依赖
- Milvus standalone依赖：etcd, MinIO（内部专用，非Kosmos基础设施）

## 部署步骤

### 1. 部署Kosmos基础设施
```bash
# 启动Kosmos核心基础设施
docker compose -f docker-compose.yml up -d postgresql redis
```

### 2. 部署Milvus服务（独立）
```bash
# 启动Milvus向量数据库服务栈
docker compose -f milvus-standalone-docker-compose.yml up -d
```

### 3. 验证服务部署
```bash
# 检查Kosmos服务
docker ps | grep kosmos

# 检查Milvus服务
docker ps | grep milvus
```

### 4. 启动应用服务
在基础设施组件和Milvus运行正常后，部署应用服务（知识库后端、评估服务后端、智能体）

## 连接信息

### Kosmos服务连接
- PostgreSQL: localhost:55432
- Redis: localhost:56379
- 外部MinIO: localhost:9000

### Milvus服务连接
- Milvus gRPC: localhost:59530
- Milvus WebUI: http://localhost:9092

> **注意**：Milvus默认无身份验证，无需用户名密码，直接使用连接字符串即可。

## 管理命令

### 启动/停止Kosmos基础设施
```bash
# 启动
docker compose -f docker-compose.yml up -d

# 停止
docker compose -f docker-compose.yml down
```

### 启动/停止Milvus服务
```bash
# 启动
docker compose -f milvus-standalone-docker-compose.yml up -d

# 停止
docker compose -f milvus-standalone-docker-compose.yml down
```

## 组件隔离说明

1. Kosmos基础设施组件和Milvus服务完全隔离在独立的Docker网络中
2. Milvus内部组件（etcd、minio）仅在其内部网络通信，不与Kosmos基础设施组件冲突
3. 若现有系统中已有MinIO服务，则Milvus会使用其内部的专用MinIO实例
4. 端口冲突风险已通过使用不同的主机端口映射消除