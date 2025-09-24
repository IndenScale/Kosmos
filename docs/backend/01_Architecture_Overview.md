# 1. Kosmos 后端架构概览

Kosmos 后端系统采用“**API服务 + 异步任务系统**”的经典模型，旨在实现高内聚、低耦合、可伸缩的架构。该设计确保了系统的核心业务逻辑与资源密集型任务的有效分离，为未来的功能扩展（如智能Agent）提供了坚实的基础。

## 核心组件

系统主要由以下几个部分构成：

1.  **双入口FastAPI应用**:
    *   **公共API (`main.py`)**: 面向最终用户和客户端应用，处理身份验证、知识空间管理、文档交互等核心业务。所有路由均需通过严格的认证和授权检查。
    *   **内部API (`internal_main.py`)**: 面向系统内部的Worker和管理员，处理文档处理回调、数据清理、系统监控等内部任务。该API由独立的密钥保护，不暴露于公网。

2.  **异步任务系统 (Dramatiq + Redis)**:
    *   所有耗时和资源密集型任务（如文档解析转换、VLM/LLM分析、未来的Chunking和Tagging）都被设计为后台任务，由Dramatiq任务队列驱动。
    *   这种设计确保了API可以快速响应用户请求，同时为系统的可伸缩性和鲁棒性提供了保障。

3.  **核心服务依赖**:
    *   **数据库 (SQLAlchemy)**: 支持PostgreSQL或SQLite，负责所有元数据（用户信息、文档结构、任务状态等）的持久化。
    *   **对象存储 (Minio)**: 负责所有二进制文件（原始文件、处理后资产、规范化内容）的存储，实现了数据与元数据的分离。
    *   **缓存/消息队列 (Redis)**: 同时用作Dramatiq的任务Broker和应用层的分布式缓存（如VLM分析结果、分布式锁）。

## 架构图

```mermaid
graph TD
    subgraph "用户/客户端"
        User[用户]
    end

    subgraph "Kosmos 后端服务"
        subgraph "API 网关 (FastAPI)"
            PublicAPI[Public API<br>(main.py)]
            InternalAPI[Internal API<br>(internal_main.py)]
        end

        subgraph "异步任务系统 (Dramatiq)"
            TaskBroker[Dramatiq Broker]
            Worker[Dramatiq Workers<br>(document_processing.py, ...)]
        end
    end

    subgraph "核心依赖服务"
        DB[(Database<br>PostgreSQL/SQLite)]
        Minio[(Object Storage<br>Minio)]
        Redis[(Cache & Broker<br>Redis)]
    end
    
    subgraph "外部工具"
        MinerU[MinerU]
        LibreOffice[LibreOffice]
    end

    User -- HTTPS --> PublicAPI
    PublicAPI -- 创建任务 --> TaskBroker
    TaskBroker -- 分发任务 --> Worker
    Worker -- 调用 --> MinerU
    Worker -- 调用 --> LibreOffice
    Worker -- 处理完成回调 --> InternalAPI
    
    PublicAPI -- 读写元数据 --> DB
    InternalAPI -- 读写元数据 --> DB
    Worker -- 读写元数据 --> DB
    
    PublicAPI -- 读写文件 --> Minio
    Worker -- 读写文件 --> Minio
    
    TaskBroker -- 使用 --> Redis
    Worker -- 使用 --> Redis
    PublicAPI -- 使用 --> Redis

```

## 设计哲学

*   **关注点分离 (Separation of Concerns)**: 公共和内部API的分离、数据与元数据的分离、同步与异步任务的分离，使得系统各部分职责清晰，易于维护和独立扩展。
*   **异步优先 (Async-First)**: 任何可能超过几百毫秒的操作都被设计为异步任务，保证了用户交互的流畅性。
*   **状态驱动 (State-Driven)**: 核心对象（如`Document`, `Job`）都有明确的状态字段（如`status`），它们的流转驱动了整个系统的业务流程。
*   **幂等性 (Idempotency)**: 关键的内部接口（如文档处理回调）被设计为幂等的，即使重复调用也能保证数据的一致性，增强了系统的鲁棒性。

## 典型工作流：文档上传

1.  用户通过 **Public API** 上传一个文档。
2.  `document_service` 计算文件哈希，检查是否内容已存在（去重），在 **DB** 中创建`Original`和`Document`记录，并将文件上传到 **Minio**。
3.  `document_service` 向 **Dramatiq Broker (Redis)** 发送一个`process_document_pipeline`任务。
4.  **Worker** 从队列中获取任务，根据文档类型（PDF, DOCX等）执行相应的处理流程（如调用**LibreOffice**或**MinerU**）。
5.  Worker 将处理结果（规范化内容、提取的图片资产）上传到 **Minio**。
6.  Worker 通过 **Internal API** 发送一个处理完成的回调。
7.  **Internal API** 接收回调，验证请求，并在 **DB** 中更新`Document`的状态、创建`Asset`记录、并建立它们之间的链接。
