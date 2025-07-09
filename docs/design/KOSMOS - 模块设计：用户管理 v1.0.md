## **1\. 概述**

用户管理模块负责处理用户的注册、登录、认证、授权以及信息管理。它是整个系统安全和权限控制的基础。

## **2\. 数据模型 (SQLite)**

CREATE TABLE users (  
    id TEXT PRIMARY KEY,            \-- UUID  
    username TEXT UNIQUE NOT NULL,  
    email TEXT UNIQUE NOT NULL,  
    password\_hash TEXT NOT NULL,  
    role TEXT NOT NULL DEFAULT 'user', \-- 'system\_admin' or 'user'  
    created\_at DATETIME DEFAULT CURRENT\_TIMESTAMP,  
    is\_active BOOLEAN DEFAULT TRUE  
);

## **3\. API 端点设计**

| 方法 | 路径 | 描述 | 所需权限 |
| :---- | :---- | :---- | :---- |
| POST | /api/v1/auth/register | 用户注册 | 公开 |
| POST | /api/v1/auth/token | 用户登录，获取JWT | 公开 |
| GET | /api/v1/users/me | 获取当前用户信息 | 已登录用户 |
| PUT | /api/v1/users/me | 更新当前用户信息 | 已登录用户 |
| GET | /api/v1/users/ | 获取所有用户列表 | 系统管理员 |
| PUT | /api/v1/users/{user\_id}/role | 更新指定用户的系统角色 | 系统管理员 |

## **4\. 核心流程与时序图**

### **4.1. 用户登录与JWT获取**

这是系统中最常见的认证流程。用户通过用户名和密码换取一个有时效性的JSON Web Token (JWT)，后续所有需要认证的请求都将携带此Token。

sequenceDiagram  
    participant User  
    participant API as "POST /auth/token"  
    participant AuthService  
    participant UserRepo as "UserRepository"  
      
    User-\>\>+API: 提供 username 和 password  
    API-\>\>+AuthService: validate\_user(username, password)  
    AuthService-\>\>+UserRepo: get\_user\_by\_username(username)  
    UserRepo--\>\>-AuthService: 返回用户信息 (含 password\_hash)  
      
    alt 用户存在且密码正确  
        AuthService-\>\>AuthService: 校验密码哈希  
        AuthService--\>\>API: 用户有效  
        API-\>\>+AuthService: create\_access\_token(user\_id, role)  
        AuthService--\>\>-API: 生成 JWT Token  
        API--\>\>-User: 返回 JWT Token  
    else 用户不存在或密码错误  
        AuthService--\>\>API: 抛出认证异常  
        API--\>\>-User: 返回 401 Unauthorized  
    end

### **4.2. 接口权限校验**

FastAPI的依赖注入系统非常适合实现RBAC。我们将创建一个依赖函数 get\_current\_user，它会解析请求头中的JWT，验证其有效性，并返回当前用户对象。然后，可以基于此创建更细粒度的权限依赖。

**示例：实现“仅系统管理员访问”的依赖**

\# auth/dependencies.py

from fastapi import Depends, HTTPException, status  
from models.user import User

\# 假设 get\_current\_active\_user 已经实现了JWT解析和用户获取  
from .auth\_service import get\_current\_active\_user 

def get\_system\_admin(current\_user: User \= Depends(get\_current\_active\_user)):  
    if current\_user.role \!= "system\_admin":  
        raise HTTPException(  
            status\_code=status.HTTP\_403\_FORBIDDEN,  
            detail="The user doesn't have enough privileges",  
        )  
    return current\_user

**在API中的使用：**

\# routers/users.py

@router.get("/", response\_model=List\[UserPublic\])  
def read\_users(  
    admin: User \= Depends(get\_system\_admin),  
    \# ...  
):  
    \# 此处代码只有系统管理员才能执行  
    return user\_service.get\_all\_users()

