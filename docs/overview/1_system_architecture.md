# 1. 系统宏观架构

Kosmos 作为一个完整的知识管理系统，其宏观架构由四个主要部分组成，它们协同工作，为用户提供从数据上传到智能检索的端到端体验。

```mermaid
graph TD
    subgraph 用户端 (User Interface)
        A[Web UI]
    end

    subgraph Kosmos 后端服务 (Backend Service)
        B(FastAPI App)
    end

    subgraph 核心依赖 (Core Dependencies)
        C[PostgreSQL]
        D[Milvus]
    end

    subgraph 外部模型服务 (Model-as-a-Service)
        E[Embedding/Reranker/LLM/VLM]
    end

    A -- HTTP API Requests --> B
    B -- 存储/读取元数据 --> C
    B -- 存储/检索向量 --> D
    B -- 调用模型能力 --> E
```

## 组件说明

### 1. 用户端 (User Interface)

-   **Web UI**: 这是用户与 Kosmos 系统交互的主要入口。它是一个现代化的单页应用（SPA），负责提供所有功能的图形化界面，包括用户登录、知识库管理、文件上传、搜索结果展示等。前端通过调用后端暴露的 HTTP API 来完成所有操作。

### 2. Kosmos 后端服务 (Backend Service)

-   **FastAPI App**: 这是整个系统的核心，基于 Python 和 FastAPI 框架构建。它负责处理所有业务逻辑，包括：
    -   **API 接口**: 提供 RESTful API 供前端或其他客户端调用。
    -   **用户认证与权限管理**: 验证用户身份，并确保用户只能访问其有权访问的资源。
    -   **业务逻辑处理**: 执行知识库、文档、解析、索引和搜索等所有核心操作。
    -   **任务调度**: 将耗时的操作（如解析、索引）放入异步任务队列中执行，避免阻塞 API 请求。
    -   **与依赖服务交互**: 连接并操作 PostgreSQL 和 Milvus 数据库。
    -   **与模型服务集成**: 调用外部的 AI 模型服务来获取 embedding、标签或其他智能分析结果。

### 3. 核心依赖 (Core Dependencies)

-   **PostgreSQL**: 作为主关系型数据库，负责持久化存储系统的所有结构化和元数据。这包括：
    -   用户信息、知识库配置、成员关系。
    -   逻辑文档和物理文档的记录。
    -   解析后的片段（Fragment）及其元数据。
    -   文本片段的索引信息（如标签）。

-   **Milvus**: 作为专业的向量数据库，负责存储由 Embedding 模型生成的向量数据。它为高效的语义相似度搜索提供了底层支持，是实现“语义化”核心价值的关键。

### 4. 外部模型服务 (Model-as-a-Service, MaaS)

-   **Embedding/Reranker/LLM/VLM**: Kosmos 本身不包含大型 AI 模型，而是通过 API 调用外部的模型服务。这种“可插拔”的设计带来了极大的灵活性：
    -   **Embedding 模型**: 用于将文本片段转换为高维向量。
    -   **Reranker 模型**: (可选) 用于对初步搜索结果进行二次重排序，提升精度。
    -   **LLM (大语言模型)**: 用于高级任务，如根据文本内容和标签字典自动生成标签。
    -   **VLM (视觉语言模型)**: 用于解析图片内容（如图表、截图），将其转换为可被索引和搜索的文本描述，是实现多模态知识理解的关键。

    系统通过**凭证管理**和**知识库模型配置**功能，允许用户为不同的知识库灵活配置不同的模型服务，以适应各种成本和性能需求。
