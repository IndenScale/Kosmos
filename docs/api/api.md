# API文档

## 用户管理

### 注册

```json
{
  "username": "testuser",
  "email": "test@example.com",
  "password": "securepassword"
}
```

response

```json
{
  "id": "ead284f9-586c-458a-a048-548288c05f95",
  "username": "testuser",
  "email": "test@example.com",
  "role": "user",
  "created_at": "2025-06-08T02:15:12",
  "is_active": true
}
```

### 登陆

```json
{
    "username": "testuser"
    "password": "securepassword"
}
```

response

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJlYWQyODRmOS01ODZjLTQ1OGEtYTA0OC01NDgyODhjMDVmOTUiLCJyb2xlIjoidXNlciIsImV4cCI6MTc0OTM1MDc2NX0.IzauoFneCa__gFRHFlzf_DVjBlSQxg2xB96bJ8yiJTA",
  "token_type": "bearer"
}
```
