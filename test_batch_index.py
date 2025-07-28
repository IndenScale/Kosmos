#!/usr/bin/env python3
"""
测试批量索引端点的脚本
"""

import asyncio
import httpx
import json
from typing import List, Dict, Any

# 配置
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"

async def test_batch_index_endpoints():
    """测试批量索引端点"""
    
    async with httpx.AsyncClient() as client:
        print("🚀 开始测试批量索引端点...")
        
        # 测试数据
        test_kb_id = "test-kb-001"
        test_fragment_ids = ["frag-001", "frag-002", "frag-003"]
        test_document_ids = ["doc-001", "doc-002"]
        
        # 1. 测试单个Fragment索引
        print("\n1️⃣ 测试单个Fragment索引...")
        try:
            response = await client.post(
                f"{API_BASE}/index/fragment/{test_fragment_ids[0]}",
                json={
                    "force_regenerate": False,
                    "max_tags": 20,
                    "enable_multimodal": False
                }
            )
            print(f"   状态码: {response.status_code}")
            if response.status_code == 200:
                print(f"   响应: {response.json()}")
            else:
                print(f"   错误: {response.text}")
        except Exception as e:
            print(f"   异常: {e}")
        
        # 2. 测试基于Fragment ID的批量索引
        print("\n2️⃣ 测试基于Fragment ID的批量索引...")
        try:
            response = await client.post(
                f"{API_BASE}/index/batch/fragments",
                json={
                    "fragment_ids": test_fragment_ids,
                    "force_regenerate": False,
                    "max_tags": 20,
                    "enable_multimodal": False
                }
            )
            print(f"   状态码: {response.status_code}")
            if response.status_code == 200:
                print(f"   响应: {response.json()}")
            else:
                print(f"   错误: {response.text}")
        except Exception as e:
            print(f"   异常: {e}")
        
        # 3. 测试基于Document ID的批量索引
        print("\n3️⃣ 测试基于Document ID的批量索引...")
        try:
            response = await client.post(
                f"{API_BASE}/index/batch/documents",
                json={
                    "document_ids": test_document_ids,
                    "force_regenerate": False,
                    "max_tags": 20,
                    "enable_multimodal": False
                }
            )
            print(f"   状态码: {response.status_code}")
            if response.status_code == 200:
                print(f"   响应: {response.json()}")
            else:
                print(f"   错误: {response.text}")
        except Exception as e:
            print(f"   异常: {e}")
        
        # 4. 测试向后兼容的批量索引端点
        print("\n4️⃣ 测试向后兼容的批量索引端点...")
        try:
            response = await client.post(
                f"{API_BASE}/index/batch",
                json={
                    "fragment_ids": test_fragment_ids,
                    "force_regenerate": False,
                    "max_tags": 20
                }
            )
            print(f"   状态码: {response.status_code}")
            if response.status_code == 200:
                print(f"   响应: {response.json()}")
            else:
                print(f"   错误: {response.text}")
        except Exception as e:
            print(f"   异常: {e}")
        
        # 5. 测试索引统计
        print("\n5️⃣ 测试索引统计...")
        try:
            response = await client.get(f"{API_BASE}/index/kb/{test_kb_id}/stats")
            print(f"   状态码: {response.status_code}")
            if response.status_code == 200:
                print(f"   响应: {response.json()}")
            else:
                print(f"   错误: {response.text}")
        except Exception as e:
            print(f"   异常: {e}")
        
        # 6. 测试列出已索引的Fragment
        print("\n6️⃣ 测试列出已索引的Fragment...")
        try:
            response = await client.get(
                f"{API_BASE}/index/kb/{test_kb_id}/fragments",
                params={"skip": 0, "limit": 10}
            )
            print(f"   状态码: {response.status_code}")
            if response.status_code == 200:
                print(f"   响应: {response.json()}")
            else:
                print(f"   错误: {response.text}")
        except Exception as e:
            print(f"   异常: {e}")
        
        print("\n✅ 批量索引端点测试完成!")

def print_api_summary():
    """打印API端点总结"""
    print("\n📋 批量索引API端点总结:")
    print("=" * 60)
    
    endpoints = [
        {
            "method": "POST",
            "path": "/api/v1/index/fragment/{fragment_id}",
            "description": "为单个Fragment创建索引",
            "body": {
                "force_regenerate": False,
                "max_tags": 20,
                "enable_multimodal": False,
                "multimodal_config": None
            }
        },
        {
            "method": "POST", 
            "path": "/api/v1/index/batch/fragments",
            "description": "基于Fragment ID列表批量创建索引",
            "body": {
                "fragment_ids": ["frag-001", "frag-002"],
                "force_regenerate": False,
                "max_tags": 20,
                "enable_multimodal": False,
                "multimodal_config": None
            }
        },
        {
            "method": "POST",
            "path": "/api/v1/index/batch/documents", 
            "description": "基于Document ID列表批量创建索引",
            "body": {
                "document_ids": ["doc-001", "doc-002"],
                "force_regenerate": False,
                "max_tags": 20,
                "enable_multimodal": False,
                "multimodal_config": None
            }
        },
        {
            "method": "POST",
            "path": "/api/v1/index/batch",
            "description": "向后兼容的批量索引端点（重定向到fragments）",
            "body": {
                "fragment_ids": ["frag-001", "frag-002"],
                "force_regenerate": False,
                "max_tags": 20
            }
        },
        {
            "method": "GET",
            "path": "/api/v1/index/kb/{kb_id}/stats",
            "description": "获取知识库索引统计"
        },
        {
            "method": "DELETE",
            "path": "/api/v1/index/fragment/{fragment_id}",
            "description": "删除Fragment索引"
        },
        {
            "method": "DELETE",
            "path": "/api/v1/index/document/{document_id}",
            "description": "删除文档的所有索引"
        },
        {
            "method": "GET",
            "path": "/api/v1/index/kb/{kb_id}/fragments",
            "description": "列出已索引的Fragment"
        }
    ]
    
    for i, endpoint in enumerate(endpoints, 1):
        print(f"\n{i}. {endpoint['method']} {endpoint['path']}")
        print(f"   描述: {endpoint['description']}")
        if 'body' in endpoint:
            print(f"   请求体示例:")
            print(f"   {json.dumps(endpoint['body'], indent=6, ensure_ascii=False)}")

if __name__ == "__main__":
    print("🔧 批量索引端点测试工具")
    print("=" * 60)
    
    # 打印API总结
    print_api_summary()
    
    # 运行测试
    print("\n" + "=" * 60)
    asyncio.run(test_batch_index_endpoints())