# Kosmos API v1 文档

本文档提供了 Kosmos 后端 API 的详细参考。所有端点都以 `/api/v1` 为前缀。

## 目录

1.  [核心工作流示例](#核心工作流示例)
2.  [身份认证](#1-身份认证)
3.  [用户管理](#2-用户管理)
4.  [知识库](#3-知识库)
5.  [模型凭证](#4-模型凭证)
6.  [文档管理](#5-文档管理)
7.  [片段管理](#6-片段管理)
8.  [解析器](#7-解析器)
9.  [索引管理](#8-索引管理)
10. [搜索](#9-搜索)
11. [任务管理](#10-任务管理)

---

## 核心工作流示例

以下是一个典型的端到端工作流，展示了如何使用 Kosmos API 完成从创建知识库到最终进行搜索的完整过程。

**第 1 步: 登录**
获取用于后续所有请求的 `access_token`。
```bash
# 请求
curl -X POST "http://127.0.0.1:8000/api/v1/auth/login" -H "Content-Type: application/json" -d '{"username": "testuser", "password": "yoursecurepassword"}'

# 响应 (记下 access_token)
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  ...
}
```

**第 2 步: 创建知识库**
创建一个用于存放文档的容器。
```bash
# 请求 (记下响应中的 id，例如 "kb_a1b2c3d4e5f6")
curl -X POST "http://127.0.0.1:8000/api/v1/kbs/" -H "Authorization: Bearer <access_token>" -H "Content-Type: application/json" -d '{"name": "项目文档知识库"}'
```

**第 3 步: 上传文档**
将一个 PDF 文件上传到新创建的知识库中。
```bash
# 请求 (记下响应中的 id，例如 "doc_b2c3d4e5f6a1")
curl -X POST "http://127.0.0.1:8000/api/v1/kbs/kb_a1b2c3d4e5f6/documents" -H "Authorization: Bearer <access_token>" -F "file=@/path/to/your/document.pdf"
```

**第 4 步: 解析文档**
触发文档解析，将其分解为可处理的文本和图像片段。
```bash
# 请求
curl -X POST "http://127.0.0.1:8000/api/v1/parser/kb/kb_a1b2c3d4e5f6/parse" -H "Authorization: Bearer <access_token>" -H "Content-Type: application/json" -d '{"document_id": "doc_b2c3d4e5f6a1"}'

# 响应 (显示解析出的片段数量)
{
  "document_id": "doc_b2c3d4e5f6a1",
  "total_fragments": 58,
  ...
}
```

**第 5 步: 检查解析状态 (可选)**
轮询此端点，直到 `status` 变为 `completed`。
```bash
# 请求
curl -X GET "http://127.0.0.1:8000/api/v1/documents/kb_a1b2c3d4e5f6/documents/doc_b2c3d4e5f6a1/status" -H "Authorization: Bearer <access_token>"
```

**第 6 步: 索引文档**
为文档的所有文本片段创建搜索索引（生成向量和标签）。这是一个后台任务。
```bash
# 请求 (记下响应中的 job_id)
curl -X POST "http://127.0.0.1:8000/api/v1/index/batch/documents" -H "Authorization: Bearer <access_token>" -H "Content-Type: application/json" -d '{"document_ids": ["doc_b2c3d4e5f6a1"]}'
```

**第 7 步: 检查索引任务状态 (可选)**
使用上一步的 `job_id` 轮询作业状态，直到 `status` 变为 `completed`。
```bash
# 请求
curl -X GET "http://127.0.0.1:8000/api/v1/jobs/<job_id>" -H "Authorization: Bearer <access_token>"
```

**第 8 步: 搜索**
一切准备就绪，现在可以在知识库中进行语义搜索。
```bash
# 请求
curl -X POST "http://127.0.0.1:8000/api/v1/kbs/kb_a1b2c3d4e5f6/search" -H "Authorization: Bearer <access_token>" -H "Content-Type: application/json" -d '{"query": "如何配置数据库连接？"}'
```

---

## 1. 身份认证

**标签:** `authentication`
**路由:** `/api/v1/auth`

### 1.2 用户登录 (详细示例)

这是与 Kosmos API 交互的第一步。成功登录后，您将获得一个 `access_token`，必须在后续所有需要授权的请求头中携带它。

**示例 cURL 请求:**
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/auth/login" \
-H "Content-Type: application/json" \
-d '{
  "username": "testuser",
  "password": "yoursecurepassword"
}'
```

**请求详解:**
- **方法:** `POST`
- **路径:** `/api/v1/auth/login`
- **请求体:** (`UserLogin` schema)
  ```json
  {
    "username": "string",
    "password": "string"
  }
  ```

**响应详解:**
- **状态码:** `200 OK`
- **响应体:** (`Token` schema)
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "user": {
      "id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
      "username": "testuser",
      "email": "test@example.com",
      "role": "user",
      "created_at": "2025-07-28T10:00:00.000Z",
      "is_active": true
    }
  }
  ```
**注解:**
- `access_token` 是有时效性的，过期后需要使用 `refresh_token` 来获取新的 `access_token`。
- 在后续所有需要授权的请求的 HTTP Header 中，必须包含 `Authorization: Bearer <your_access_token>`。

---
## 3. 知识库
### 3.1 创建知识库 (详细示例)

创建一个新的知识库容器。成功后返回的 `id` 将用于后续所有与该知识库相关的操作，如上传文档、配置模型等。

**示例 cURL 请求:**
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/kbs/" \
-H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
-H "Content-Type: application/json" \
-d '{
  "name": "我的第一个知识库",
  "description": "用于测试API工作流",
  "is_public": false
}'
```

**请求详解:**
- **方法:** `POST`
- **路径:** `/api/v1/kbs/`
- **路径参数:** `kb_id` (必需) - 目标知识库的 ID。
- **Header:** `Authorization: Bearer <your_access_token>` (必需)
- **请求体:** (`KBCreate` schema)
  ```json
  {
    "name": "string",
    "description": "string (optional)",
    "is_public": boolean (optional, default: false)
  }
  ```

**响应详解:**
- **状态码:** `201 Created`
- **响应体:** (`KBResponse` schema)
  ```json
  {
    "id": "kb_a1b2c3d4e5f6",
    "name": "我的第一个知识库",
    "description": "用于测试API工作流",
    "owner_id": "user_a1b2c3d4",
    "tag_dictionary": {},
    "milvus_collection_id": "kb_a1b2c3d4e5f6",
    "is_public": false,
    "last_tag_dictionary_update_time": null,
    "created_at": "2025-07-28T10:05:00.000Z"
  }
  ```
**注解:**
- 响应中的 `id` 是此知识库的唯一标识符，请务必保存以用于后续操作。

### 3.6 更新标签字典 (详细示例)

配置知识库的标签体系。这个字典定义了在后续索引过程中，AI 可以为文本片段生成的候选标签。一个结构良好的标签字典是提升后续检索质量的关键。

**示例 cURL 请求:**
```bash
curl -X PUT "http://127.0.0.1:8000/api/v1/kbs/kb_a1b2c3d4e5f6/tags" \
-H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
-H "Content-Type: application/json" \
-d '{
  "tag_dictionary": {
    "功能模块": [
      "用户管理",
      "订单处理",
      "支付网关"
    ],
    "技术栈": {
      "前端": ["React", "Vue", "Angular"],
      "后端": ["FastAPI", "Node.js", "Java"]
    },
    "文档类型": "API文档"
  }
}'
```

**请求详解:**
- **方法:** `PUT`
- **路径:** `/api/v1/kbs/{kb_id}/tags`
- **路径参数:** `kb_id` (必需) - 目标知识库的 ID。
- **Header:** `Authorization: Bearer <your_access_token>` (必需)
- **请求体:** (`TagDictionaryUpdate` schema)
  ```json
  {
    "tag_dictionary": {
      "key": "value",
      "nested_key": { ... }
    }
  }
  ```

**响应详解:**
- **状态码:** `200 OK`
- **响应体:** (`KBResponse` schema)，其中 `tag_dictionary` 字段已被更新。

---
## 5. 文档管理
### 5.1 上传文档 (详细示例)

将文件上传到指定的知识库。这是知识进入系统的入口。

**示例 cURL 请求:**
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/kbs/kb_a1b2c3d4e5f6/documents" \
-H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
-F "file=@/path/to/your/document.pdf"
```

**请求详解:**
- **方法:** `POST`
- **路径:** `/api/v1/kbs/{kb_id}/documents`
- **路径参数:** `kb_id` (必需) - 目标知识库的 ID。
- **Header:** `Authorization: Bearer <your_access_token>` (必需)
- **请求体:** `multipart/form-data`
  - `file`: (必需) - 要上传的文件。

**响应详解:**
- **状态码:** `200 OK`
- **响应体:** (`DocumentResponse` schema)
  ```json
  {
    "id": "doc_b2c3d4e5f6a1",
    "filename": "document.pdf",
    "file_type": "application/pdf",
    "created_at": "2025-07-28T10:15:00.000Z",
    "file_size": 1234567,
    "file_url": ""
  }
  ```
**注解:**
- 响应中的 `id` 是此文档的唯一标识符，用于后续的解析和索引操作。
- `file_url` 仅对系统管理员可见，普通用户为空。

---
## 7. 解析器
### 7.1 解析文档 (详细示例)

触发对已上传文档的解析。此过程会将文档内容分解为多个片段（`Fragment`），例如文本段落、图片、表格等。这是进行索引和搜索的前提。

**示例 cURL 请求:**
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/parser/kb/kb_a1b2c3d4e5f6/parse" \
-H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
-H "Content-Type: application/json" \
-d '{
  "document_id": "doc_b2c3d4e5f6a1",
  "force_reparse": false
}'
```

**请求详解:**
- **方法:** `POST`
- **路径:** `/api/v1/parser/kb/{kb_id}/parse`
- **路径参数:** `kb_id` (必需) - 文档所在的知识库 ID。
- **Header:** `Authorization: Bearer <your_access_token>` (必需)
- **请求体:** (`DocumentParseRequest` schema)
  ```json
  {
    "document_id": "string",
    "force_reparse": boolean (optional, default: false)
  }
  ```

**响应详解:**
- **状态码:** `200 OK`
- **响应体:** (`ParseResponse` schema)
  ```json
  {
    "document_id": "doc_b2c3d4e5f6a1",
    "total_fragments": 58,
    "text_fragments": 45,
    "screenshot_fragments": 10,
    "figure_fragments": 3,
    "parse_duration_ms": 15230,
    "success": true,
    "error_message": null
  }
  ```
**注解:**
- 这是一个同步等待的端点，但后台是异步处理。对于大文件，请求可能会耗时较长。
- 对于生产环境中的大批量任务，推荐使用 `POST /kb/{kb_id}/batch-parse` 端点，它会立即返回一个作业 ID。

### 7.3 获取解析状态 (详细示例)

检查特定文档的解析状态，确认其是否已完成解析、是否成功，并查看生成的片段数量。

**示例 cURL 请求:**
```bash
curl -X GET "http://127.0.0.1:8000/api/v1/parser/document/doc_b2c3d4e5f6a1/status" \
-H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**请求详解:**
- **方法:** `GET`
- **路径:** `/api/v1/parser/document/{document_id}/status`
- **路径参数:** `document_id` (必需) - 目标文档的 ID。
- **Header:** `Authorization: Bearer <your_access_token>` (必需)

**响应详解:**
- **状态码:** `200 OK`
- **响应体:** (`ParseStatusResponse` schema)
  ```json
  {
    "document_id": "doc_b2c3d4e5f6a1",
    "status": "completed",
    "last_parsed_at": "2025-07-28T10:20:00.000Z",
    "fragment_count": 58,
    "error_message": null
  }
  ```
**注解:**
- 在触发解析后，可以轮询此端点以监控解析进度。
- `status` 字段可以帮助判断是解析成功 (`completed`)、失败 (`failed`) 还是从未解析过 (`unknown`)。
- 另一个有用的状态检查端点是 `GET /kbs/{kb_id}/documents/{document_id}/status`，它提供了更详细的索引进度。
