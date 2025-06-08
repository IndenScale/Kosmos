import pytest
import json
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@pytest.fixture
def auth_token():
    with open('tests/user/access_token.json') as f:
        return json.load(f)['access_token']

class TestKnowledgeBase:
    def test_create_knowledge_base(self, auth_token):
        response = client.post(
            "/api/v1/knowledge_bases",
            json={"name": "测试知识库", "description": "测试用知识库"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 201
        assert "id" in response.json()

    def test_get_knowledge_bases(self, auth_token):
        response = client.get(
            "/api/v1/knowledge_bases",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)