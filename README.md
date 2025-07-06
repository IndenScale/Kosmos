# Kosmos

Kosmos 是一个现代化的知识管理系统，旨在提供一个全面的解决方案，用于文档的摄取、存储、管理和语义搜索。它采用前后端分离的架构，后端使用 FastAPI 构建，前端则由 React 实现。

近期，**Kosmos 引入了流式领域主题模型（SDTM）作为其核心认知智能引擎**，使知识库从被动的"数据仓库"升级为能够自我优化的"智慧体"。

## 核心功能

* **知识库管理**: 用户可以创建、更新和删除知识库，并管理知识库的成员及其角色（所有者、管理员、成员）。知识库可以是公开的或私有的。
* **文档管理**: 支持多种格式的文档上传，包括 PDF、TXT、Markdown、DOC 和 DOCX。 系统采用内容寻址存储（通过 SHA256 哈希）来自动去重。
* **文档摄取**: 提供一个异步处理流水线，用于将原始文档转换为结构化的、可搜索的"片段"(Chunks)。
* **语义搜索**: 用户可以执行复杂的语义搜索，结合了向量搜索和标签过滤的功能，以提供精确和相关的搜索结果。
* **用户认证**: 提供基于 JWT 的安全认证系统，包括用户注册和登录功能。
* **智能主题模型 (SDTM)**: Kosmos 的核心创新。它是一个认知智能引擎，旨在解决知识库的两个根本挑战：
    * **标签体系的持续演进**: SDTM 能够根据新摄入的文档，自动分析并优化知识库的标签字典，使其能够自我进化，保持与时俱进。
    * **文档的智能标注**: 利用大语言模型（LLM）实现对文档的自动化、高一致性标签标注，取代了繁琐的手动操作。
    * **提供三种可控的运行模式**:
        * **编辑模式 (Edit)**: 完全应用LLM的建议，同时优化标签字典并为文档打标。
        * **标注模式 (Annotation)**: 仅为文档打标，而不改变现有的标签体系。
        * **影子模式 (Shadow)**: 纯预览模式，在不修改任何数据的情况下，评估和预览优化方案可能带来的效果。

## 技术架构

Kosmos 系统由多个核心组件构成，包括一个 FastAPI 后端、一个 React 前端、一个用于存储元数据的 SQLite 数据库，以及一个用于向量搜索的 Milvus 数据库。**SDTM 引擎作为认知核心，深度集成在后端服务层中**。

### 后端

后端采用三层架构模式，由 FastAPI 构建，确保了逻辑解耦和高可维护性。

* **API 层 (Routers)**: 负责处理 HTTP 请求，使用 Pydantic 模型进行数据验证，并调用相应的服务层方法。
* **服务层 (Services)**: 包含核心业务逻辑，例如文档上传、知识库创建和语义搜索。
* **数据访问层 (Repositories)**: 负责与 SQLite、Milvus 和本地文件存储进行交互，将底层数据操作封装起来。

### 前端

前端是一个使用 Create React App 搭建的单页应用，利用 React、Ant Design 和 Zustand 等技术来提供丰富的用户交互界面。

* **路由**: 使用 `react-router-dom` 进行页面导航。
* **状态管理**: 使用 Zustand 来管理应用的全局状态，例如用户信息。
* **数据请求**: 通过 `axios` 和 `@tanstack/react-query` 与后端 API 进行通信。

## 安装与启动

### 环境要求

* Node.js
* Python 3.7+
* Docker (推荐，用于运行 Milvus)

### 后端启动

1.  **安装依赖**:
    ```bash
    pip install -r requirements.txt
    ```
2.  **配置环境变量**:
    在项目根目录下创建一个 `.env` 文件，并根据需要配置以下变量：
    ```
    OPENAI_API_KEY="your-openai-api-key"
    OPENAI_BASE_URL="your-openai-base-url"
    MILVUS_HOST="localhost"
    MILVUS_PORT="19530"
    ```
3.  **启动应用**:
    ```bash
    uvicorn app.main:app --reload
    ```
    应用将在 `http://localhost:8000` 上运行。

### 前端启动

1.  **进入前端目录**:
    ```bash
    cd frontend
    ```
2.  **安装依赖**:
    ```bash
    npm install
    ```
3.  **启动应用**:
    ```bash
    npm start
    ```
    前端开发服务器将在 `http://localhost:3001` 上运行。

## API 端点

Kosmos 提供了一系列 RESTful API 端点用于与系统交互。

### 用户认证

* **`POST /api/v1/auth/register`**: 用户注册。
* **`POST /api/v1/auth/token`**: 用户登录并获取访问令牌。

### 知识库

* **`POST /api/v1/kbs/`**: 创建一个新的知识库。
* **`GET /api/v1/kbs/`**: 列出当前用户参与的所有知识库。
* **`GET /api/v1/kbs/{kb_id}`**: 获取特定知识库的详细信息。

### 文档管理

* **`POST /api/v1/kbs/{kb_id}/documents`**: 上传一个新文档到指定的知识库。
* **`GET /api/v1/kbs/{kb_id}/documents`**: 列出指定知识库中的所有文档。
* **`DELETE /api/v1/kbs/{kb_id}/documents/{doc_id}`**: 从知识库中移除一个文档。

### 文档摄取

* **`POST /api/v1/kbs/{kb_id}/documents/{doc_id}/ingest`**: 为指定文档创建一个摄取任务。
* **`GET /api/v1/jobs/{job_id}`**: 获取摄取任务的状态。

### 语义搜索

* **`POST /api/v1/kbs/{kb_id}/search`**: 在指定的知识库中执行复合语义搜索。

### 智能主题模型 (SDTM)

* **`POST /api/v1/sdtm/{kb_id}/jobs`**: 启动一个SDTM优化任务，可配置运行模式及相关参数。
* **`GET /api/v1/sdtm/{job_id}`**: 获取指定SDTM任务的状态和结果。
* **`GET /api/v1/sdtm/{kb_id}/stats`**: 获取知识库的SDTM相关统计数据和健康状况。

## 许可

该项目根据 MIT 许可证授权。详情请参阅 `LICENSE` 文件。