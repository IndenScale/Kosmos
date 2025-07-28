"""
Fragment管理功能测试脚本
文件: test_fragment_management.py
创建时间: 2025-07-26
描述: 测试fragment管理和解析功能
"""

import requests
import json
from typing import Dict, Any

class FragmentTestClient:
    """Fragment测试客户端"""

    def __init__(self, base_url: str = "http://localhost:8000", token: str = None):
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}

    def get_kb_fragments(self, kb_id: str, fragment_type: str = None, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """获取知识库Fragment列表"""
        url = f"{self.base_url}/api/v1/fragments/kb/{kb_id}"
        params = {"page": page, "page_size": page_size}
        if fragment_type:
            params["fragment_type"] = fragment_type

        response = requests.get(url, headers=self.headers, params=params)
        return response.json()

    def get_document_fragments(self, document_id: str, fragment_type: str = None) -> Dict[str, Any]:
        """获取文档Fragment列表"""
        url = f"{self.base_url}/api/v1/fragments/document/{document_id}"
        params = {}
        if fragment_type:
            params["fragment_type"] = fragment_type

        response = requests.get(url, headers=self.headers, params=params)
        return response.json()

    def get_fragment(self, fragment_id: str) -> Dict[str, Any]:
        """获取Fragment详情"""
        url = f"{self.base_url}/api/v1/fragments/{fragment_id}"
        response = requests.get(url, headers=self.headers)
        return response.json()

    def update_fragment(self, fragment_id: str, meta_info: Dict[str, Any]) -> Dict[str, Any]:
        """更新Fragment"""
        url = f"{self.base_url}/api/v1/fragments/{fragment_id}"
        data = {"meta_info": meta_info}
        response = requests.put(url, headers=self.headers, json=data)
        return response.json()

    def get_kb_fragment_stats(self, kb_id: str) -> Dict[str, Any]:
        """获取知识库Fragment统计"""
        url = f"{self.base_url}/api/v1/fragments/kb/{kb_id}/stats"
        response = requests.get(url, headers=self.headers)
        return response.json()

    def parse_document_fragments(self, document_id: str, kb_id: str, force_reparse: bool = False) -> Dict[str, Any]:
        """解析文档Fragment"""
        url = f"{self.base_url}/api/v1/fragments/parse"
        data = {
            "document_id": document_id,
            "kb_id": kb_id,
            "force_reparse": force_reparse
        }
        response = requests.post(url, headers=self.headers, json=data)
        return response.json()

    def batch_parse_documents(self, kb_id: str, document_ids: list, force_reparse: bool = False) -> Dict[str, Any]:
        """批量解析文档Fragment"""
        url = f"{self.base_url}/api/v1/fragments/batch-parse"
        params = {"kb_id": kb_id, "force_reparse": force_reparse}
        response = requests.post(url, headers=self.headers, params=params, json=document_ids)
        return response.json()


def test_fragment_management():
    """测试Fragment管理功能"""
    # 注意：需要先获取有效的token和ID
    client = FragmentTestClient(token="your_token_here")

    kb_id = "your_kb_id_here"
    document_id = "your_document_id_here"

    print("=== Fragment管理功能测试 ===")

    # 1. 测试获取知识库Fragment统计
    print("\n1. 获取知识库Fragment统计:")
    try:
        stats = client.get_kb_fragment_stats(kb_id)
        print(f"统计结果: {json.dumps(stats, indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"获取统计失败: {e}")

    # 2. 测试解析文档Fragment
    print("\n2. 解析文档Fragment:")
    try:
        parse_result = client.parse_document_fragments(document_id, kb_id)
        print(f"解析结果: {json.dumps(parse_result, indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"解析失败: {e}")

    # 3. 测试获取知识库Fragment列表
    print("\n3. 获取知识库Fragment列表:")
    try:
        fragments = client.get_kb_fragments(kb_id, page=1, page_size=10)
        print(f"Fragment列表: {json.dumps(fragments, indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"获取列表失败: {e}")

    # 4. 测试获取文档Fragment列表
    print("\n4. 获取文档Fragment列表:")
    try:
        doc_fragments = client.get_document_fragments(document_id)
        print(f"文档Fragment: {json.dumps(doc_fragments, indent=2, ensure_ascii=False)}")

        # 如果有Fragment，测试更新功能
        if doc_fragments and len(doc_fragments) > 0:
            fragment_id = doc_fragments[0]["id"]
            print(f"\n5. 测试更新Fragment {fragment_id}:")

            # 测试禁用Fragment
            update_result = client.update_fragment(fragment_id, {"activated": False})
            print(f"更新结果: {json.dumps(update_result, indent=2, ensure_ascii=False)}")

    except Exception as e:
        print(f"获取文档Fragment失败: {e}")


if __name__ == "__main__":
    test_fragment_management()