# 4. Kosmos API 设计与安全机制

Kosmos 的 API 设计遵循 RESTful 原则，并利用 FastAPI 的依赖注入系统实现了一套强大而灵活的安全机制。系统通过分离公共和内部API，以及精细化的权限控制，确保了数据的安全和访问的合规性。

## API 入口

系统包含两个独立的 FastAPI 应用实例，以实现关注点分离：

*   **`main.py` (公共API)**:
    *   **访问地址**: `http://localhost:8011`
    *   **用途**: 面向最终用户和第三方应用，提供核心业务功能，如用户管理、知识空间、文档操作等。
    *   **安全**: 所有端点（除登录和注册外）都受到 OAuth2 Password Bearer 方案的保护，要求提供有效的 JWT (JSON Web Token)。

*   **`internal_main.py` (内部API)**:
    *   **访问地址**: `http://localhost:8012`
    *   **用途**: 面向内部的后台Worker和管理脚本，提供数据回调、管理和维护等高权限操作。
    *   **安全**: 通过自定义的 API Key Header (`X-Internal-Secret`) 进行保护。该密钥在系统内部共享，不应暴露给外部用户。

## 认证 (Authentication)

认证是验证用户身份的过程。Kosmos 主要采用基于 JWT 的 Token 认证机制。

1.  **登录**: 用户通过 `/api/v1/auth/token` 端点，使用用户名（或邮箱）和密码进行登录。
2.  **Token签发**: `auth.py` 中的 `login_for_access_token` 函数会验证用户凭据。成功后，`security.py` 中的 `create_access_token` 函数会生成一个 JWT。
    *   **Payload**: Token 的载荷（payload）中包含了用户的唯一标识 `user_id` (`sub` 字段) 和过期时间 `exp`。
    *   **签名**: 使用 `settings.SECRET_KEY` 和 `HS256` 算法进行签名，防止Token被篡改。
    *   **有效期**: 普通用户 Token 有效期为30分钟，超级管理员 (`super_admin`) 的 Token 有效期为7天，提供了更强的便利性。
3.  **后续请求**: 客户端在后续请求的 `Authorization` Header 中携带此 Token (`Bearer <token>`)。

## 授权 (Authorization)

授权是在用户身份被确认后，判断其是否有权执行特定操作的过程。Kosmos 利用 FastAPI 的依赖注入（`Depends`）实现了一套分层、可复用的授权检查机制，主要在 `dependencies.py` 中定义。

### 1. 获取当前用户

*   **`get_current_user(token: str = Depends(oauth2_scheme))`**:
    *   这是所有需要登录的端点的基础依赖。
    *   它从 `Authorization` Header 中解析出 JWT，验证其签名和有效期，并从中提取 `user_id`。
    *   然后使用 `user_id` 从数据库中查询出完整的 `User` 对象。
    *   如果 Token 无效或用户不存在，则直接抛出 `401 Unauthorized` 异常。

### 2. 角色与权限检查

Kosmos 的权限模型是基于用户在特定**知识空间**中的**角色**。

*   **`get_member_or_404(...)`**:
    *   **作用**: 检查当前登录用户是否是指定知识空间的成员。
    *   **逻辑**: 在 `knowledge_space_members` 表中查找 `(knowledge_space_id, user_id)` 的组合。
    *   **结果**: 如果是成员，则返回 `KnowledgeSpaceMember` 对象（包含了用户的角色信息）；如果不是，则抛出 `404 Not Found` 异常（出于安全考虑，不明确告知是“无权限”还是“不存在”）。

*   **`require_role(allowed_roles: List[str])`**:
    *   **作用**: 这是一个依赖**工厂**，它返回一个用于检查角色的依赖项。这使得权限检查非常富有表现力。
    *   **用法**: 在路由中，可以这样使用 `Depends(require_role(["owner", "editor"]))`。
    *   **逻辑**: 它首先依赖于 `get_member_or_404` 来获取用户的成员身份和角色，然后检查该角色是否在 `allowed_roles` 列表中。如果不在，则抛出 `403 Forbidden` 异常。

*   **`require_super_admin(...)`**:
    *   **作用**: 一个专门的依赖，用于检查用户是否是系统级的超级管理员。
    *   **逻辑**: 直接检查 `current_user.role` 字段是否为 `"super_admin"`。如果不是，则抛出 `403 Forbidden` 异常。

### 3. 资源访问验证

除了角色检查，系统还确保用户只能访问其有权访问的特定资源（如文档、资产）。

*   **`get_document_and_verify_membership(...)`**:
    *   **作用**: 获取一个 `Document` 对象，并同时验证当前用户是否是该文档所属知识空间的成员。
    *   **逻辑**: 它首先根据 `document_id` 查找文档，如果找到，则从文档对象中获取 `knowledge_space_id`，然后内部调用 `get_member_or_404` 来进行成员资格检查。
    *   **优势**: 将“获取资源”和“验证权限”两个步骤合二为一，简化了路由函数的逻辑，并避免了代码重复。

## 其他安全措施

*   **密码哈希**: `security.py` 使用 `passlib` 库的 `bcrypt` 算法对用户密码进行加盐哈希存储，确保即使数据库泄露，密码也无法被轻易破解。
*   **凭证加密**: `security.py` 使用 `cryptography.fernet` 对称加密算法，将用户存储的第三方AI服务API Key (`ModelCredential.encrypted_api_key`) 进行加密，保护了用户的敏感凭证。
*   **内部API密钥**: `internal_dependencies.py` 中的 `get_internal_api_key` 依赖项负责从 `X-Internal-Secret` Header 中读取并验证内部API密钥，确保只有受信任的内部服务（如Worker）才能调用这些高权限接口。
