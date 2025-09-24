# Kosmos 公共 API (Public API)

本文档描述了面向最终用户和前端应用的公共 API 端点。

- **服务地址**: `http://localhost:8011`
- **认证方式**: JWT (JSON Web Token)

---

## 1. 认证 (Authentication)
- **Prefix**: `/api/v1/auth`
- **路由文件**: `backend/app/routers/auth.py`

| 方法   | 路径                  | 描述                 |
| ------ | --------------------- | -------------------- |
| `POST` | `/register`           | 用户注册             |
| `POST` | `/login`              | 用户登录，获取 JWT   |
| `GET`  | `/users/me`           | 获取当前用户信息     |

---

## 2. 用户 (Users)
- **Prefix**: `/api/v1/users`
- **路由文件**: `backend/app/routers/users.py`

| 方法   | 路径                  | 描述                 |
| ------ | --------------------- | -------------------- |
| `GET`  | `/{user_id}`          | 获取指定用户信息     |

---

## 3. 知识空间 (Knowledge Spaces)
- **Prefix**: `/api/v1/knowledge-spaces`
- **路由文件**: `backend/app/routers/knowledge_spaces.py`

| 方法   | 路径                  | 描述                 |
| ------ | --------------------- | -------------------- |
| `POST` | `/`                   | 创建新的知识空间     |
| `GET`  | `/`                   | 列出用户所属的知识空间 |
| `GET`  | `/{space_id}`         | 获取知识空间详情     |
| `PUT`  | `/{space_id}`         | 更新知识空间信息     |
| `DELETE`| `/{space_id}`        | 删除知识空间         |
| `POST` | `/{space_id}/members` | 添加知识空间成员     |
| `GET`  | `/{space_id}/members` | 列出知识空间成员     |
| `DELETE`| `/{space_id}/members/{user_id}` | 移除知识空间成员 |

---

## 4. 文档 (Documents)
- **Prefix**: `/api/v1/documents`
- **路由文件**: `backend/app/routers/documents.py`

| 方法   | 路径                  | 描述                 |
| ------ | --------------------- | -------------------- |
| `POST` | `/upload`             | 上传新文档           |
| `GET`  | `/{document_id}`           | 获取文档详情和状态   |
| `DELETE`| `/{document_id}`          | 删除文档             |
