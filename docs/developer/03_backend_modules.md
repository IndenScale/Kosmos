# 开发者文档：03 - 后端模块深入解析

本章旨在深入剖析 Kosmos 后端（位于 `/app` 目录）的代码结构，帮助开发者快速定位功能、理解各模块的职责，并遵循项目现有的设计模式进行高效开发。

后端采用分层架构，将不同的职责清晰地分离到各自的目录中。

## 目录结构总览

```
/app
├── main.py             # FastAPI 应用入口
├── config.py           # 应用配置加载
├── db/                 # 数据库相关
│   └── database.py     # 数据库会话管理
├── dependencies/       # FastAPI 依赖项注入
│   └── auth.py         # 认证依赖
├── models/             # SQLAlchemy ORM 模型
│   ├── user.py
│   └── ...
├── processors/         # 文档处理器
│   ├── base_processor.py
│   └── ...
├── repositories/       # 数据访问层
│   ├── document_repo.py
│   └── ...
├── routers/            # API 路由层
│   ├── documents.py
│   └── ...
├── schemas/            # Pydantic 数据模型 (DTOs)
│   ├── document.py
│   └── ...
├── services/           # 核心业务逻辑层
│   ├── document_service.py
│   └── ...
└── utils/              # 通用工具和辅助函数
    ├── text_splitter.py
    └── ...
```

## 各模块职责详解

### `main.py`
应用的启动入口。它负责初始化 FastAPI 应用实例，挂载所有 API 路由 (`routers`)，并配置中间件（如 CORS）。

### `config.py`
负责从环境变量 (`.env` 文件) 中加载和管理应用的配置信息。这提供了一个集中的地方来处理所有配置项，如数据库连接字符串、JWT 密钥、Milvus 地址等。

### `db/`
此目录处理与数据库连接和会话相关的所有逻辑。
- **`database.py`**: 定义了 SQLAlchemy 的 `engine` 和 `SessionLocal`，并提供了一个 FastAPI 依赖 `get_db`，用于在 API 请求的生命周期内获取和管理数据库会话。

### `dependencies/`
存放 FastAPI 的可重用依赖项（Dependencies）。这些依赖项通常用于处理横切关注��，如认证、授权和权限检查。
- **`auth.py`**, **`kb_auth.py`**: 实现了获取当前用户、验证 JWT 令牌、检查用户对特定知识库的访问权限等逻辑。

### `models/`
定义了所有与数据库表对应的 SQLAlchemy ORM 模型。每个文件（如 `user.py`, `document.py`）通常对应一个数据库表，描述了其字段和关系。

### `processors/`
这是文档摄入流程中的核心组件之一，负责解析不同格式的原始文件。
- **`base_processor.py`**: 定义了所有处理器的通用接口（抽象基类）。
- **`pdf_processor.py`**, **`docx_processor.py`**, etc.: 实现了对特定文件类型（PDF, DOCX）的解析逻辑。
- **`processor_factory.py`**: 一个工厂类，能根据文件扩展名自动选择并实例化合适的处理器。

### `repositories/`
数据访问层（Repository Pattern）。它封装了与数据存储（包括 PostgreSQL 和 Milvus）交互的底层逻辑，将数据操作的复杂性与业务逻辑分离。
- **`document_repo.py`**: 封装了对 `documents` 和 `chunks` 表的增删改查操作。
- **`milvus_repo.py`**: 封装了与 Milvus 向量数据库的交���，如创建集合、插入向量、执行向量搜索等。

### `routers/`
API 路由层，直接暴露给客户端。它使用 FastAPI 的 `APIRouter` 来定义 HTTP 端点（如 `/users`, `/documents`）。
- **职责**:
    1. 定义路径、HTTP 方法（GET, POST, etc.）。
    2. 处理请求参数和路径变量。
    3. 调用 `services` 中的业务逻辑。
    4. 使用 `schemas` 来验证请求体和格式化响应。
    5. 通过依赖注入获取数据库会话和认证信息。

### `schemas/`
定义了所有用于 API 数据传输的 Pydantic 模型（也称为数据传输对象 DTOs）。
- **作用**:
    1. **数据验证**: FastAPI 用它们来自动验证传入的 JSON 请求体。
    2. **数据序列化**: 控制从数据库模型到 JSON 响应的转换，可以隐藏或添加字段。
    3. **API 文档**: FastAPI 根据这些模型自动生成清晰的 API 文档。

### `services/`
核心业务逻辑层。它编排来自 `repositories` 的数据操作，并组合成完整的业务功能。这是实现应用核心价值的地方。
- **`ingestion_service.py`**: 编排整个文档摄入流程，从调用处理器��存储数据。
- **`search_service.py`**: 实现语义搜索的完整逻辑，包括向量检索和重排。
- **`sdtm_service.py`**: 调用 `sdtm_engine` 并管理主题建模相关的任务。
- **`user_service.py`**: 处理用户注册、登录等业务。

### `utils/`
存放项目范围内的通用工具、算法和辅助函数。
- **`intelligent_text_splitter.py`**: 实现了智能文本分块算法。
- **`reranker.py`**: 封装了重排模型的调用逻辑。
- **`query_parser.py`**: 用于解析复杂的搜索查询。
- **`task_queue.py`**: 与异步任务队列（如 Celery）交互的接口。

通过理解这个结构，开发者可以轻松地追踪一个 API 请求从 `router` 到 `service` 再到 `repository` 的完整流程，并清楚地知道应该在哪个模块中添加或修改代码。
