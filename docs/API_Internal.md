# Kosmos 内部 API (Internal API)

本文档描述了用于内部服务间通信和管理员操作的 API 端点。

- **服务地址**: `http://localhost:8012`
- **认证方式**: 共享密钥 (Shared Secret)，通过 `X-Internal-Secret` 请求头传递。

---

## 1. Worker 回调 (Worker Callbacks)
- **Prefix**: `/api/v1/workers`
- **路由文件**: `backend/app/routers/workers.py`

| 方法   | 路径                     | 描述                                       |
| ------ | ------------------------ | ------------------------------------------ |
| `POST` | `/processing-callback`   | 接收 Worker 的文档处理结果（成功或失败）   |

---

## 2. 管理 - 文档 (Admin - Documents)
- **Prefix**: `/api/v1/admin/documents`
- **路由文件**: `backend/app/routers/documents_admin.py`

| 方法   | 路径                     | 描述                                       |
| ------ | ------------------------ | ------------------------------------------ |
| `POST` | `/{document_id}/reprocess`    | 手动触发对指定文档的重新处理流程           |

---

## 3. 管理 - 派生资产 (Admin - Assets)
- **Prefix**: `/api/v1/admin/assets`
- **路由文件**: `backend/app/routers/assets_admin.py`

| 方法   | 路径                     | 描述                                       |
| ------ | ------------------------ | ------------------------------------------ |
| `GET`  | `/{asset_hash}/check`    | 检查 Asset 在数据库和对象存储间的一致性    |

---

## 4. 管理 - 原始文件 (Admin - Originals)
- **Prefix**: `/api/v1/admin/originals`
- **路由文件**: `backend/app/routers/originals_admin.py`

| 方法   | 路径                     | 描述                                       |
| ------ | ------------------------ | ------------------------------------------ |
| `GET`  | `/{original_hash}/check` | 检查 Original 在数据库和对象存储间的一致性 |
