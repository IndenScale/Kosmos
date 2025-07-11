import pytest
import json
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# 测试用户信息
test_user = {
    "username": "testuser2",
    "password": "testpassword123",
    "email": "testuser@example.com"
}

# 记录测试用户信息
with open('tests/test_user.json', 'w') as f:
    f.write(json.dumps(test_user))

def test_register_user():
    # 注册用户
    response = client.post(
        "/api/v1/auth/register",
        json=test_user
    )
    assert response.status_code == 200
    assert "id" in response.json()


def test_login_user():
    # 登录获取token
    response = client.post(
        "/api/v1/auth/token",
        data={
            "username": test_user["username"],
            "password": test_user["password"]
        }
    )
    assert response.status_code == 201
    assert "access_token" in response.json()
    assert "token_type" in response.json()