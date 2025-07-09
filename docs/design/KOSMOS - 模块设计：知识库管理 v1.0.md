## **1\. 概述**

知识库管理模块负责处理知识库（Knowledge Base, KB）的创建、配置、成员管理和生命周期维护。每个KB是一个独立的数据和权限沙箱，包含了文档、标签字典和成员。

## **2\. 数据模型 (SQLite)**

\-- 知识库表  
CREATE TABLE knowledge\_bases (  
    id TEXT PRIMARY KEY,               \-- UUID  
    name TEXT NOT NULL,  
    description TEXT,  
    owner\_id TEXT NOT NULL,            \-- 关联到 users(id)  
    tag\_dictionary TEXT NOT NULL,      \-- JSON格式存储树状标签字典  
    is\_public BOOLEAN DEFAULT FALSE,   \-- 是否对访客开放只读查询  
    created\_at DATETIME DEFAULT CURRENT\_TIMESTAMP,  
    FOREIGN KEY (owner\_id) REFERENCES users(id)  
);

\-- 知识库成员表 (RBAC)  
CREATE TABLE kb\_members (  
    kb\_id TEXT NOT NULL,               \-- 关联到 knowledge\_bases(id)  
    user\_id TEXT NOT NULL,             \-- 关联到 users(id)  
    role TEXT NOT NULL,                \-- 'owner', 'admin', 'member'  
    created\_at DATETIME DEFAULT CURRENT\_TIMESTAMP,  
    PRIMARY KEY (kb\_id, user\_id),  
    FOREIGN KEY (kb\_id) REFERENCES knowledge\_bases(id) ON DELETE CASCADE,  
    FOREIGN KEY (user\_id) REFERENCES users(id) ON DELETE CASCADE  
);

## **3\. API 端点设计**

| 方法 | 路径 | 描述 | 所需权限 |
| :---- | :---- | :---- | :---- |
| POST | /api/v1/kbs/ | 创建一个新的知识库 | 已登录用户 |
| GET | /api/v1/kbs/ | 列出我参与的知识库 | 已登录用户 |
| GET | /api/v1/kbs/{kb\_id} | 获取特定知识库的详情 | KB 成员 |
| PUT | /api/v1/kbs/{kb\_id} | 更新知识库元信息 | KB Owner, Admin |
| DELETE | /api/v1/kbs/{kb\_id} | 删除知识库 | KB Owner |
| PUT | /api/v1/kbs/{kb\_id}/tags | 初始化或更新标签字典 | KB Owner |
| GET | /api/v1/kbs/{kb\_id}/members | 获取知识库成员列表 | KB Owner, Admin |
| POST | /api/v1/kbs/{kb\_id}/members | 添加/更新知识库成员 | KB Owner, Admin |
| DELETE | /api/v1/kbs/{kb\_id}/members/{user\_id} | 移除知识库成员 | KB Owner, Admin |

## **4\. RBAC 权限依赖实现**

与系统级权限类似，我们将为知识库创建专门的权限依赖项，用于检查用户对特定知识库的访问级别。

**示例：实现“仅KB管理员及以上”的依赖**

\# kbs/dependencies.py  
from fastapi import Depends, HTTPException, status  
from models.user import User  
from models.kb import KBRole  
from services.kb\_service import KBService

\# 引入用户认证依赖  
from auth.dependencies import get\_current\_active\_user 

def get\_kb\_admin\_or\_owner(  
    kb\_id: str,  
    current\_user: User \= Depends(get\_current\_active\_user),  
    kb\_service: KBService \= Depends() \# 假设KBService可被依赖注入  
):  
    member \= kb\_service.get\_member\_role(kb\_id, current\_user.id)  
    if not member or member.role not in \[KBRole.ADMIN, KBRole.OWNER\]:  
        raise HTTPException(  
            status\_code=status.HTTP\_403\_FORBIDDEN,  
            detail="User does not have Admin or Owner privileges for this KB",  
        )  
    return current\_user

## **5\. 核心流程与时序图**

### **5.1. 创建知识库**

用户创建一个新的知识库时，系统会自动将该用户设为知识库的“拥有者”（Owner）。

sequenceDiagram  
    participant User  
    participant API as "POST /kbs/"  
    participant KBService  
    participant KBRepo as "KBRepository"  
      
    User-\>\>+API: 提供 name, description  
    Note right of User: (携带JWT Token)  
      
    API-\>\>+KBService: create\_kb(name, description, owner\_id=current\_user.id)  
    KBService-\>\>KBService: 生成新的 kb\_id (UUID)  
    KBService-\>\>+KBRepo: 在事务中执行:  
    KBRepo-\>\>KBRepo: 1\. 插入到 \`knowledge\_bases\` 表  
    KBRepo-\>\>KBRepo: 2\. 插入到 \`kb\_members\` 表 (role='owner')  
    KBRepo--\>\>-KBService: 事务成功，返回新KB对象  
    KBService--\>\>-API: 返回新创建的KB信息  
    API--\>\>-User: 返回 201 Created 和 KB详情

### **5.2. 初始化标签字典**

知识库的Owner可以通过提供种子数据，调用LLM来生成一个结构化的标签字典。这是一个计算密集型操作。

sequenceDiagram  
    participant User as "KB Owner"  
    participant API as "PUT /kbs/{kb\_id}/tags"  
    participant KBService  
    participant LLMService as "LLM Service (Utils)"  
    participant KBRepo as "KBRepository"

    User-\>\>+API: 提供 seed\_tags, query\_description, seed\_documents  
    Note right of User: (拥有对kb\_id的Owner权限)

    API-\>\>+KBService: initialize\_tag\_dictionary(kb\_id, seed\_data)  
    KBService-\>\>+LLMService: generate\_tag\_dictionary(prompt)  
    Note over KBService, LLMService: KBService负责根据种子数据构建复杂的提示词(Prompt)

    LLMService--\>\>-KBService: 返回生成的JSON格式标签字典  
      
    KBService-\>\>KBService: 验证和清理返回的JSON  
    alt 验证成功  
        KBService-\>\>+KBRepo: update\_tag\_dictionary(kb\_id, new\_dict)  
        KBRepo--\>\>-KBService: 更新成功  
        KBService--\>\>-API: 返回更新后的标签字典  
        API--\>\>-User: 返回 200 OK  
    else 验证失败或LLM出错  
        KBService--\>\>-API: 抛出处理异常  
        API--\>\>-User: 返回 422 Unprocessable Entity  
    end  
