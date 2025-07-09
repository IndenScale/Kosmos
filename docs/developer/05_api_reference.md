# 开发者文档：05 - API 接口参考

Kosmos 的后端使用 FastAPI 框架构建，它的一大优势是能够根据代码自动生成交互式的 API 文档。本文档将指导您如何访问和使用这些自动生成的文档。

## 访问交互式 API 文档

当后端服务成功运行后，您可以直接通过浏览器访问两个不同的交互式 API 文档界面。

假设您的后端服务运行在 `http://localhost:8000`，那么：

1.  **Swagger UI (推荐)**
    *   **URL**: `http://localhost:8000/docs`
    *   这是一个功能非常丰富的交互式界面，您可以在这里：
        *   查看所有可用的 API 端点，按标签（通常是按 `router` 文件）分组。
        *   展开每个端点，查看其详细信息，包括：
            *   HTTP 方法 (GET, POST, PUT, DELETE 等)。
            *   所需的参数（路径、查询、请求体）。
            *   请求体和响应体的 `schema` (数据模型)。
            *   可能的响应状态码及其含义。
        *   直接在浏览器中进行 API 调用测试，无需使用 Postman 等第三方工具。

2.  **ReDoc**
    *   **URL**: `http://localhost:8000/redoc`
    *   这提供了另一种风格的文档界面，更加紧凑和易于阅读，但不支持交互式 API 调用。它非常适合用于快速查阅和理解 API 的结构。

## API 认证

大部分需要操作用户数据或知识库内容的 API 端点都是受保护的，需要提供认证信息。Kosmos 使用 JWT (JSON Web Tokens) 进行认证。

在 Swagger UI 中进行测试时，请遵循以下步骤：

1.  **获取 Token**:
    *   访问 `/auth/token` 端点 (通常是一个 `POST` 请求)。
    *   在请求体中提供您的用户名 (`username`) 和密码 (`password`)。
    *   执行请求后，您将获得一个 `access_token`。

2.  **授权后续请求**:
    *   在 Swagger UI 页面的右上角，点击 "Authorize" 按钮。
    *   在弹出的窗口中，将您获得的 `access_token` 粘贴到 "Value" 输入框中，格式为 `Bearer <your_token>` (注意 `Bearer` 和 token 之间的空格)。
    *   点击 "Authorize" 保存。

完成此操作后，您在该页面上发出的所有后续 API 请求都将自动在请求头中附带 `Authorization` 信息。

## API 设计原则

Kosmos 的 API 设计遵循 RESTful 风格，并利用了 FastAPI 的特性：

- **资源导向**: API 路径以资源名词的复数形式组织 (e.g., `/knowledge-bases`, `/documents`)。
- **清晰的 HTTP 方法**:
    - `GET`: 用于检索资源。
    - `POST`: 用于创建新资源。
    - `PUT` / `PATCH`: 用于更新现有资源。
    - `DELETE`: 用于删除资源。
- **Pydantic Schemas**: 所有请求和响应的数据结构都由 `schemas/` 目录下的 Pydantic 模型严格定义，这保证了数据的一致性和可靠性，并为自动文档生成提供了基础。
- **依赖注入**: 使用 FastAPI 的依赖注入系统来处理数据库会话 (`get_db`) 和用户认证 (`get_current_user`)，使路由函数保持干净和专注。

我们强烈建议您在进行后端开发时，始终保持浏览器打开 `/docs` 页面。它是理解 API、测试变更和调试问题的最快、最有效的方式。
