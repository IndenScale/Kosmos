#!/usr/bin/env python3
"""
Kosmos Knowledge Base MCP Server

一个用于访问远程Kosmos知识库的MCP服务器，提供语义搜索和知识库查询功能。
"""

import asyncio
import json
import os
from typing import Any, Sequence, Optional, List, Dict
from urllib.parse import urljoin
import aiohttp
from dotenv import load_dotenv

from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    LoggingLevel
)
from pydantic.networks import AnyUrl
import mcp.types as types

# 加载环境变量
load_dotenv()

class KosmosClient:
    """Kosmos API客户端"""
    
    def __init__(self, base_url: str, username: Optional[str] = None, password: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.session: Optional[aiohttp.ClientSession] = None
        self.auth_token: Optional[str] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        await self._authenticate()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def _authenticate(self):
        """认证获取token"""
        if not self.session:
            raise Exception("Session未初始化")
            
        if self.username and self.password:
            # 使用与auth.py一致的token端点
            auth_url = urljoin(self.base_url, '/api/v1/auth/token')
            auth_data = {
                'username': self.username,
                'password': self.password
            }
            try:
                # 使用form data而不是json，与OAuth2PasswordRequestForm保持一致
                async with self.session.post(auth_url, data=auth_data) as response:
                    if response.status == 200:
                        result = await response.json()
                        self.auth_token = result.get('access_token')
                        if not self.auth_token:
                            print(f"警告: 认证响应中未找到access_token: {result}")
                    elif response.status == 401:
                        print(f"认证失败: 用户名或密码错误")
                    else:
                        response_text = await response.text()
                        print(f"认证失败: HTTP {response.status} - {response_text}")
            except Exception as e:
                print(f"认证过程出错: {e}")
                # 如果认证失败，尝试不使用认证（对于公共知识库）
                pass
    
    def _get_headers(self):
        """获取请求头"""
        headers = {'Content-Type': 'application/json'}
        if self.auth_token:
            headers['Authorization'] = f'Bearer {self.auth_token}'
        return headers
    
    async def list_knowledge_bases(self) -> List[Dict]:
        """列出知识库"""
        if not self.session:
            raise Exception("Session未初始化")
            
        url = urljoin(self.base_url, '/api/v1/kbs/')
        headers = self._get_headers()
        
        async with self.session.get(url, headers=headers) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 401:
                raise Exception(f"未授权访问: 请检查用户名和密码配置")
            elif response.status == 403:
                raise Exception(f"禁止访问: 用户没有权限访问知识库列表")
            else:
                response_text = await response.text()
                raise Exception(f"获取知识库列表失败: HTTP {response.status} - {response_text}")
    
    async def get_knowledge_base(self, kb_id: str) -> Dict:
        """获取知识库详情"""
        if not self.session:
            raise Exception("Session未初始化")
            
        url = urljoin(self.base_url, f'/api/v1/kbs/{kb_id}')
        headers = self._get_headers()
        
        async with self.session.get(url, headers=headers) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 401:
                raise Exception(f"未授权访问: 请检查认证配置")
            elif response.status == 403:
                raise Exception(f"禁止访问: 用户没有权限访问知识库 {kb_id}")
            elif response.status == 404:
                raise Exception(f"知识库 {kb_id} 不存在")
            else:
                response_text = await response.text()
                raise Exception(f"获取知识库详情失败: HTTP {response.status} - {response_text}")
    
    async def search_knowledge_base(self, kb_id: str, query: str, top_k: int = 10) -> Dict:
        """在知识库中执行语义搜索
        
        支持复合查询语法：
        - 普通词汇：直接匹配
        - +词汇：必须包含
        - -词汇：必须排除 
        - ~标签：按标签过滤
        """
        if not self.session:
            raise Exception("Session未初始化")
            
        url = urljoin(self.base_url, f'/api/v1/kbs/{kb_id}/search')
        headers = self._get_headers()
        data = {
            'query': query,
            'top_k': top_k
        }
        
        async with self.session.post(url, json=data, headers=headers) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 401:
                raise Exception(f"未授权访问: 请检查认证配置")
            elif response.status == 403:
                raise Exception(f"禁止访问: 用户没有权限搜索知识库 {kb_id}")
            elif response.status == 404:
                raise Exception(f"知识库 {kb_id} 不存在")
            elif response.status == 422:
                response_text = await response.text()
                raise Exception(f"搜索参数错误: {response_text}")
            else:
                response_text = await response.text()
                raise Exception(f"搜索失败: HTTP {response.status} - {response_text}")
    
    async def get_chunk(self, chunk_id: str) -> Dict:
        """根据ID获取chunk详情"""
        if not self.session:
            raise Exception("Session未初始化")
            
        url = urljoin(self.base_url, f'/api/v1/chunks/{chunk_id}')
        headers = self._get_headers()
        
        async with self.session.get(url, headers=headers) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 401:
                raise Exception(f"未授权访问: 请检查认证配置")
            elif response.status == 404:
                raise Exception(f"文档片段 {chunk_id} 不存在")
            else:
                response_text = await response.text()
                raise Exception(f"获取chunk失败: HTTP {response.status} - {response_text}")
    
    async def get_knowledge_base_stats(self, kb_id: str) -> Dict:
        """获取知识库统计信息"""
        if not self.session:
            raise Exception("Session未初始化")
            
        url = urljoin(self.base_url, f'/api/v1/kbs/{kb_id}/stats')
        headers = self._get_headers()
        
        async with self.session.get(url, headers=headers) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 401:
                raise Exception(f"未授权访问: 请检查认证配置")
            elif response.status == 403:
                raise Exception(f"禁止访问: 用户没有权限访问知识库 {kb_id} 的统计信息")
            elif response.status == 404:
                raise Exception(f"知识库 {kb_id} 不存在")
            else:
                response_text = await response.text()
                raise Exception(f"获取知识库统计失败: HTTP {response.status} - {response_text}")
    
    async def get_knowledge_base_health(self, kb_id: str) -> Dict:
        """获取知识库健康度监测信息（SDTM统计）"""
        if not self.session:
            raise Exception("Session未初始化")
            
        url = urljoin(self.base_url, f'/api/v1/sdtm/{kb_id}/stats')
        headers = self._get_headers()
        
        async with self.session.get(url, headers=headers) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 401:
                raise Exception(f"未授权访问: 请检查认证配置")
            elif response.status == 403:
                raise Exception(f"禁止访问: 用户没有权限访问知识库 {kb_id} 的健康度信息")
            elif response.status == 404:
                raise Exception(f"知识库 {kb_id} 不存在")
            else:
                response_text = await response.text()
                raise Exception(f"获取知识库健康度失败: HTTP {response.status} - {response_text}")
    
    async def get_abnormal_documents(self, kb_id: str, limit: int = 3) -> Dict:
        """获取异常文档列表（限制数量以避免上下文污染）"""
        if not self.session:
            raise Exception("Session未初始化")
            
        url = urljoin(self.base_url, f'/api/v1/sdtm/{kb_id}/abnormal-documents')
        headers = self._get_headers()
        
        async with self.session.get(url, headers=headers) as response:
            if response.status == 200:
                result = await response.json()
                # 按异常类型分组并限制每类的数量
                if result.get('abnormal_documents'):
                    grouped = {}
                    for doc in result['abnormal_documents']:
                        anomaly_type = doc.get('anomaly_type', 'unknown')
                        if anomaly_type not in grouped:
                            grouped[anomaly_type] = []
                        if len(grouped[anomaly_type]) < limit:
                            grouped[anomaly_type].append(doc)
                    
                    # 重新组织结果
                    result['abnormal_documents_by_type'] = grouped
                    result['abnormal_documents'] = []
                    for docs in grouped.values():
                        result['abnormal_documents'].extend(docs)
                
                return result
            elif response.status == 401:
                raise Exception(f"未授权访问: 请检查认证配置")
            elif response.status == 403:
                raise Exception(f"禁止访问: 用户没有权限访问知识库 {kb_id} 的异常文档")
            elif response.status == 404:
                raise Exception(f"知识库 {kb_id} 不存在")
            else:
                response_text = await response.text()
                raise Exception(f"获取异常文档失败: HTTP {response.status} - {response_text}")
    
    async def start_health_optimization(self, kb_id: str, mode: str = "shadow", batch_size: int = 10) -> Dict:
        """启动知识库健康度优化任务"""
        if not self.session:
            raise Exception("Session未初始化")
            
        url = urljoin(self.base_url, f'/api/v1/sdtm/{kb_id}/optimize')
        headers = self._get_headers()
        data = {
            'mode': mode,
            'batch_size': batch_size,
            'auto_apply': mode != 'shadow',  # 影子模式不自动应用
            'abnormal_doc_slots': 3,
            'normal_doc_slots': 7,
            'max_iterations': 50,
            'abnormal_doc_threshold': 3.0,
            'enable_early_termination': True
        }
        
        async with self.session.post(url, json=data, headers=headers) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 401:
                raise Exception(f"未授权访问: 请检查认证配置")
            elif response.status == 403:
                raise Exception(f"禁止访问: 用户没有权限启动知识库 {kb_id} 的优化任务")
            elif response.status == 404:
                raise Exception(f"知识库 {kb_id} 不存在")
            else:
                response_text = await response.text()
                raise Exception(f"启动优化任务失败: HTTP {response.status} - {response_text}")
    
    async def get_optimization_jobs(self, kb_id: str) -> Dict:
        """获取知识库优化任务列表"""
        if not self.session:
            raise Exception("Session未初始化")
            
        url = urljoin(self.base_url, f'/api/v1/sdtm/{kb_id}/jobs')
        headers = self._get_headers()
        
        async with self.session.get(url, headers=headers) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 401:
                raise Exception(f"未授权访问: 请检查认证配置")
            elif response.status == 403:
                raise Exception(f"禁止访问: 用户没有权限访问知识库 {kb_id} 的任务列表")
            elif response.status == 404:
                raise Exception(f"知识库 {kb_id} 不存在")
            else:
                response_text = await response.text()
                raise Exception(f"获取任务列表失败: HTTP {response.status} - {response_text}")
    
    async def get_optimization_job_status(self, kb_id: str, job_id: str) -> Dict:
        """获取优化任务状态"""
        if not self.session:
            raise Exception("Session未初始化")
            
        url = urljoin(self.base_url, f'/api/v1/sdtm/{kb_id}/jobs/{job_id}')
        headers = self._get_headers()
        
        async with self.session.get(url, headers=headers) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 401:
                raise Exception(f"未授权访问: 请检查认证配置")
            elif response.status == 403:
                raise Exception(f"禁止访问: 用户没有权限访问任务 {job_id}")
            elif response.status == 404:
                raise Exception(f"任务 {job_id} 不存在")
            else:
                response_text = await response.text()
                raise Exception(f"获取任务状态失败: HTTP {response.status} - {response_text}")
    
    async def get_tagging_stats(self, kb_id: str) -> Dict:
        """获取标签统计信息"""
        if not self.session:
            raise Exception("Session未初始化")
            
        url = urljoin(self.base_url, f'/api/v1/tagging/{kb_id}/stats')
        headers = self._get_headers()
        
        async with self.session.get(url, headers=headers) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 401:
                raise Exception(f"未授权访问: 请检查认证配置")
            elif response.status == 403:
                raise Exception(f"禁止访问: 用户没有权限访问知识库 {kb_id} 的标签统计")
            elif response.status == 404:
                raise Exception(f"知识库 {kb_id} 不存在")
            else:
                response_text = await response.text()
                raise Exception(f"获取标签统计失败: HTTP {response.status} - {response_text}")
    
    async def get_untagged_chunks(self, kb_id: str, limit: int = 10) -> Dict:
        """获取未标注的文档片段"""
        if not self.session:
            raise Exception("Session未初始化")
            
        url = urljoin(self.base_url, f'/api/v1/tagging/{kb_id}/untagged-chunks')
        headers = self._get_headers()
        params = {'limit': limit}
        
        async with self.session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 401:
                raise Exception(f"未授权访问: 请检查认证配置")
            elif response.status == 403:
                raise Exception(f"禁止访问: 用户没有权限访问知识库 {kb_id} 的未标注片段")
            elif response.status == 404:
                raise Exception(f"知识库 {kb_id} 不存在")
            else:
                response_text = await response.text()
                raise Exception(f"获取未标注片段失败: HTTP {response.status} - {response_text}")
    
    async def start_tagging_task(self, kb_id: str, document_id: str = None, chunk_ids: list = None) -> Dict:
        """启动标注任务"""
        if not self.session:
            raise Exception("Session未初始化")
            
        if document_id:
            url = urljoin(self.base_url, f'/api/v1/tagging/{kb_id}/tag-document/{document_id}')
            data = {}
        else:
            url = urljoin(self.base_url, f'/api/v1/tagging/{kb_id}/tag-chunks')
            data = {'chunk_ids': chunk_ids} if chunk_ids else {}
        
        headers = self._get_headers()
        
        async with self.session.post(url, json=data, headers=headers) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 401:
                raise Exception(f"未授权访问: 请检查认证配置")
            elif response.status == 403:
                raise Exception(f"禁止访问: 用户没有权限启动标注任务")
            elif response.status == 404:
                raise Exception(f"知识库 {kb_id} 不存在")
            else:
                response_text = await response.text()
                raise Exception(f"启动标注任务失败: HTTP {response.status} - {response_text}")
    
    async def get_document_screenshots(self, document_id: str) -> Dict:
        """获取文档截图信息"""
        if not self.session:
            raise Exception("Session未初始化")
            
        url = urljoin(self.base_url, f'/screenshots/document/{document_id}')
        headers = self._get_headers()
        
        async with self.session.get(url, headers=headers) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 401:
                raise Exception(f"未授权访问: 请检查认证配置")
            elif response.status == 404:
                raise Exception(f"文档 {document_id} 不存在或无截图")
            else:
                response_text = await response.text()
                raise Exception(f"获取文档截图失败: HTTP {response.status} - {response_text}")
    
    async def get_screenshot_info(self, screenshot_id: str) -> Dict:
        """获取截图详细信息"""
        if not self.session:
            raise Exception("Session未初始化")
            
        url = urljoin(self.base_url, f'/screenshots/{screenshot_id}/info')
        headers = self._get_headers()
        
        async with self.session.get(url, headers=headers) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 401:
                raise Exception(f"未授权访问: 请检查认证配置")
            elif response.status == 404:
                raise Exception(f"截图 {screenshot_id} 不存在")
            else:
                response_text = await response.text()
                raise Exception(f"获取截图信息失败: HTTP {response.status} - {response_text}")

# 创建MCP服务器实例
server = Server("kosmos-knowledge-base")

@server.list_resources()
async def handle_list_resources() -> list[Resource]:
    """列出可用的资源"""
    return [
        Resource(
            uri=AnyUrl("kosmos://knowledge-bases"),
            name="知识库列表",
            description="获取所有可访问的知识库列表",
            mimeType="application/json"
        )
    ]

@server.read_resource()
async def handle_read_resource(uri: AnyUrl) -> str:
    """读取资源内容"""
    if str(uri) == "kosmos://knowledge-bases":
        base_url = os.getenv('KOSMOS_BASE_URL')
        if not base_url:
            return "错误: 未配置KOSMOS_BASE_URL环境变量"
            
        try:
            async with KosmosClient(
                base_url=base_url,
                username=os.getenv('KOSMOS_USERNAME'),
                password=os.getenv('KOSMOS_PASSWORD'),
            ) as client:
                kbs = await client.list_knowledge_bases()
                return json.dumps(kbs, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"获取知识库列表失败: {str(e)}"
    else:
        raise ValueError(f"未知资源: {uri}")

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """列出可用的工具"""
    return [
        Tool(
            name="list_knowledge_bases",
            description="列出所有可访问的知识库",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_knowledge_base",
            description="获取指定知识库的详细信息",
            inputSchema={
                "type": "object",
                "properties": {
                    "kb_id": {
                        "type": "string",
                        "description": "知识库ID"
                    }
                },
                "required": ["kb_id"]
            }
        ),
        Tool(
            name="search_knowledge_base",
            description="在指定知识库中进行语义搜索，支持标签过滤",
            inputSchema={
                "type": "object",
                "properties": {
                    "kb_id": {
                        "type": "string",
                        "description": "知识库ID"
                    },
                    "query": {
                        "type": "string",
                        "description": "搜索查询，支持复合查询语法：普通词汇、+必须包含、-必须排除、~标签过滤（如：'AI未来发展 +技术 -历史 ~应用'）"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回结果数量（最多50）",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50
                    }
                },
                "required": ["kb_id", "query"]
            }
        ),
        Tool(
            name="get_chunk",
            description="根据ID获取文档片段的详细信息",
            inputSchema={
                "type": "object",
                "properties": {
                    "chunk_id": {
                        "type": "string",
                        "description": "文档片段ID"
                    }
                },
                "required": ["chunk_id"]
            }
        ),
        Tool(
            name="get_knowledge_base_stats",
            description="获取知识库的统计信息",
            inputSchema={
                "type": "object",
                "properties": {
                    "kb_id": {
                        "type": "string",
                        "description": "知识库ID"
                    }
                },
                "required": ["kb_id"]
            }
        ),
        Tool(
            name="monitor_knowledge_base_health",
            description="监测知识库健康度，检查标签质量、文档标注状态等指标",
            inputSchema={
                "type": "object",
                "properties": {
                    "kb_id": {
                        "type": "string",
                        "description": "知识库ID"
                    }
                },
                "required": ["kb_id"]
            }
        ),
        Tool(
            name="get_problematic_documents",
            description="获取有问题的文档列表，包括标注不足、标注过度、无法区分的文档",
            inputSchema={
                "type": "object",
                "properties": {
                    "kb_id": {
                        "type": "string",
                        "description": "知识库ID"
                    },
                    "samples_per_type": {
                        "type": "integer",
                        "description": "每种异常类型返回的样本数量",
                        "default": 3,
                        "minimum": 1,
                        "maximum": 10
                    }
                },
                "required": ["kb_id"]
            }
        ),
        Tool(
            name="start_health_optimization",
            description="启动知识库健康度优化任务，可以选择影子模式（仅分析）或编辑模式（自动修复）",
            inputSchema={
                "type": "object",
                "properties": {
                    "kb_id": {
                        "type": "string",
                        "description": "知识库ID"
                    },
                    "mode": {
                        "type": "string",
                        "description": "优化模式：shadow（影子模式，仅分析不修改）、edit（编辑模式，自动修复）",
                        "enum": ["shadow", "edit"],
                        "default": "shadow"
                    },
                    "batch_size": {
                        "type": "integer",
                        "description": "批处理大小",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50
                    }
                },
                "required": ["kb_id"]
            }
        ),
        Tool(
            name="get_optimization_jobs",
            description="获取知识库优化任务列表和状态",
            inputSchema={
                "type": "object",
                "properties": {
                    "kb_id": {
                        "type": "string",
                        "description": "知识库ID"
                    }
                },
                "required": ["kb_id"]
            }
        ),
        Tool(
            name="get_optimization_job_status",
            description="获取特定优化任务的详细状态",
            inputSchema={
                "type": "object",
                "properties": {
                    "kb_id": {
                        "type": "string",
                        "description": "知识库ID"
                    },
                    "job_id": {
                        "type": "string",
                        "description": "任务ID"
                    }
                },
                "required": ["kb_id", "job_id"]
            }
        ),
        Tool(
            name="get_tagging_overview",
            description="获取知识库标签管理概览，包括标注统计和未标注内容",
            inputSchema={
                "type": "object",
                "properties": {
                    "kb_id": {
                        "type": "string",
                        "description": "知识库ID"
                    }
                },
                "required": ["kb_id"]
            }
        ),
        Tool(
            name="get_untagged_content",
            description="获取需要标注的未标注文档片段",
            inputSchema={
                "type": "object",
                "properties": {
                    "kb_id": {
                        "type": "string",
                        "description": "知识库ID"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回的片段数量",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50
                    }
                },
                "required": ["kb_id"]
            }
        ),
        Tool(
            name="start_smart_tagging",
            description="启动智能标注任务，可以对整个文档或特定片段进行标注",
            inputSchema={
                "type": "object",
                "properties": {
                    "kb_id": {
                        "type": "string",
                        "description": "知识库ID"
                    },
                    "document_id": {
                        "type": "string",
                        "description": "要标注的文档ID（可选，如果指定则标注整个文档）"
                    },
                    "chunk_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要标注的片段ID列表（可选，如果指定则只标注这些片段）"
                    }
                },
                "required": ["kb_id"]
            }
        ),
        Tool(
            name="get_document_visual_preview",
            description="获取文档的可视化预览信息，包括页面截图",
            inputSchema={
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "string",
                        "description": "文档ID"
                    }
                },
                "required": ["document_id"]
            }
        ),
        Tool(
            name="get_screenshot_details",
            description="获取特定截图的详细信息",
            inputSchema={
                "type": "object",
                "properties": {
                    "screenshot_id": {
                        "type": "string",
                        "description": "截图ID"
                    }
                },
                "required": ["screenshot_id"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """处理工具调用"""
    base_url = os.getenv('KOSMOS_BASE_URL')
    if not base_url:
        return [types.TextContent(
            type="text",
            text="❌ 错误: 未配置KOSMOS_BASE_URL环境变量\n\n请在.env文件中设置:\nKOSMOS_BASE_URL=http://localhost:8000"
        )]
    
    username = os.getenv('KOSMOS_USERNAME')
    password = os.getenv('KOSMOS_PASSWORD')
    
    # 提示认证配置（但不强制要求，因为可能有公开知识库）
    auth_warning = ""
    if not username or not password:
        auth_warning = "\n⚠️  提示: 未配置KOSMOS_USERNAME或KOSMOS_PASSWORD，只能访问公开知识库"
        
    try:
        async with KosmosClient(
            base_url=base_url,
            username=username,
            password=password,
        ) as client:
            
            if name == "list_knowledge_bases":
                result = await client.list_knowledge_bases()
                return [types.TextContent(
                    type="text",
                    text=f"# 知识库列表\n\n找到 {len(result)} 个知识库：\n\n" + 
                         "\n".join([f"- **{kb['name']}** ({kb['id']}): {kb.get('description', '无描述')}" 
                                   for kb in result])
                )]
                
            elif name == "get_knowledge_base":
                kb_id = arguments["kb_id"]
                result = await client.get_knowledge_base(kb_id)
                members_info = f"成员数量: {len(result.get('members', []))}"
                return [types.TextContent(
                    type="text",
                    text=f"# 知识库详情\n\n"
                         f"**名称**: {result['name']}\n"
                         f"**ID**: {result['id']}\n"
                         f"**描述**: {result.get('description', '无描述')}\n"
                         f"**所有者**: {result.get('owner_username', result['owner_id'])}\n"
                         f"**是否公开**: {'是' if result['is_public'] else '否'}\n"
                         f"**{members_info}**\n"
                         f"**创建时间**: {result['created_at']}\n"
                         f"**标签字典**: {len(result.get('tag_dictionary', {}))} 个标签"
                )]
                
            elif name == "search_knowledge_base":
                kb_id = arguments["kb_id"]
                query = arguments["query"]
                top_k = arguments.get("top_k", 10)
                result = await client.search_knowledge_base(kb_id, query, top_k)
                
                search_results = result.get("results", [])
                recommended_tags = result.get("recommended_tags", [])
                
                response = f"# 搜索结果\n\n查询: **{query}**\n找到 {len(search_results)} 个相关结果:\n\n"
                
                for i, item in enumerate(search_results, 1):
                    tags_str = ", ".join(item.get("tags", [])) or "无标签"
                    response += f"## 结果 {i} (相似度: {item['score']:.3f})\n"
                    response += f"**文档ID**: {item['document_id']}\n"
                    response += f"**片段ID**: {item['chunk_id']}\n"
                    response += f"**标签**: {tags_str}\n"
                    response += f"**内容**:\n{item['content'][:500]}{'...' if len(item['content']) > 500 else ''}\n\n"
                
                if recommended_tags:
                    response += f"## 推荐标签\n\n"
                    for tag in recommended_tags[:5]:  # 只显示前5个推荐标签
                        response += f"- {tag['tag']} (频率: {tag['freq']}, 分数: {tag['eig_score']:.3f})\n"
                
                return [types.TextContent(type="text", text=response)]
                
            elif name == "get_chunk":
                chunk_id = arguments["chunk_id"]
                result = await client.get_chunk(chunk_id)
                tags_str = ", ".join(result.get("tags", [])) or "无标签"
                return [types.TextContent(
                    type="text",
                    text=f"# 文档片段详情\n\n"
                         f"**片段ID**: {result['id']}\n"
                         f"**知识库ID**: {result['kb_id']}\n"
                         f"**文档ID**: {result['document_id']}\n"
                         f"**片段索引**: {result['chunk_index']}\n"
                         f"**标签**: {tags_str}\n"
                         f"**创建时间**: {result['created_at']}\n\n"
                         f"**内容**:\n{result['content']}"
                )]
                
            elif name == "get_knowledge_base_stats":
                kb_id = arguments["kb_id"]
                result = await client.get_knowledge_base_stats(kb_id)
                return [types.TextContent(
                    type="text",
                    text=f"# 知识库统计信息\n\n{json.dumps(result, ensure_ascii=False, indent=2)}"
                )]
                
            elif name == "monitor_knowledge_base_health":
                kb_id = arguments["kb_id"]
                result = await client.get_knowledge_base_health(kb_id)
                
                # 格式化健康度信息
                progress = result.get('progress_metrics', {})
                quality = result.get('quality_metrics', {})
                
                response = f"# 知识库健康度监测\n\n"
                response += f"**知识库ID**: {result['kb_id']}\n"
                response += f"**最后更新**: {result.get('last_updated', 'N/A')}\n\n"
                
                # 进度指标
                response += f"## 📊 进度指标\n\n"
                response += f"- **当前迭代**: {progress.get('current_iteration', 0)}/{progress.get('total_iterations', 100)}\n"
                response += f"- **进度**: {progress.get('progress_pct', 0):.1f}%\n"
                response += f"- **标签字典大小**: {progress.get('current_tags_dictionary_size', 0)}/{progress.get('max_tags_dictionary_size', 1000)}\n"
                response += f"- **容量使用**: {progress.get('capacity_pct', 0):.1f}%\n\n"
                
                # 质量指标
                response += f"## 🔍 质量指标\n\n"
                response += f"- **标注不足的文档**: {quality.get('under_annotated_docs_count', 0)} 个\n"
                response += f"- **标注过度的文档**: {quality.get('over_annotated_docs_count', 0)} 个\n"
                response += f"- **无法区分的文档**: {quality.get('indistinguishable_docs_count', 0)} 个\n"
                response += f"- **使用不足的标签**: {quality.get('under_used_tags_count', 0)} 个\n"
                response += f"- **使用过度的标签**: {quality.get('over_used_tags_count', 0)} 个\n\n"
                
                # 异常文档概览
                abnormal_docs = result.get('abnormal_documents', [])
                if abnormal_docs:
                    response += f"## ⚠️ 异常文档概览\n\n"
                    response += f"发现 {len(abnormal_docs)} 个异常文档。使用 `get_problematic_documents` 工具查看详情。\n"
                
                return [types.TextContent(type="text", text=response)]
                
            elif name == "get_problematic_documents":
                kb_id = arguments["kb_id"]
                limit = arguments.get("samples_per_type", 3)
                result = await client.get_abnormal_documents(kb_id, limit)
                
                abnormal_docs = result.get('abnormal_documents', [])
                grouped_docs = result.get('abnormal_documents_by_type', {})
                
                response = f"# 有问题的文档\n\n"
                response += f"**知识库ID**: {kb_id}\n"
                response += f"**总异常文档数**: {result.get('total_count', len(abnormal_docs))}\n"
                response += f"**每类显示样本数**: {limit}\n\n"
                
                # 按类型显示异常文档
                type_names = {
                    'under_annotated': '标注不足',
                    'over_annotated': '标注过度',
                    'indistinguishable': '无法区分'
                }
                
                for anomaly_type, docs in grouped_docs.items():
                    type_name = type_names.get(anomaly_type, anomaly_type)
                    response += f"## {type_name}文档 ({len(docs)} 个样本)\n\n"
                    
                    for i, doc in enumerate(docs, 1):
                        content_preview = doc['content'][:200] + "..." if len(doc['content']) > 200 else doc['content']
                        tags_str = ", ".join(doc.get('current_tags', [])) or "无标签"
                        
                        response += f"### 样本 {i}\n"
                        response += f"**文档ID**: {doc['doc_id']}\n"
                        response += f"**异常原因**: {doc.get('reason', 'N/A')}\n"
                        response += f"**当前标签**: {tags_str}\n"
                        response += f"**内容预览**: {content_preview}\n\n"
                
                return [types.TextContent(type="text", text=response)]
                
            elif name == "start_health_optimization":
                kb_id = arguments["kb_id"]
                mode = arguments.get("mode", "shadow")
                batch_size = arguments.get("batch_size", 10)
                
                result = await client.start_health_optimization(kb_id, mode, batch_size)
                
                mode_desc = "影子模式（仅分析）" if mode == "shadow" else "编辑模式（自动修复）"
                response = f"# 健康度优化任务已启动\n\n"
                response += f"**知识库ID**: {kb_id}\n"
                response += f"**优化模式**: {mode_desc}\n"
                response += f"**批处理大小**: {batch_size}\n"
                response += f"**任务ID**: {result.get('job_id', 'N/A')}\n\n"
                response += f"**状态**: {result.get('message', '任务已启动')}\n\n"
                response += f"💡 使用 `get_optimization_job_status` 工具查看任务进度。"
                
                return [types.TextContent(type="text", text=response)]
                
            elif name == "get_optimization_jobs":
                kb_id = arguments["kb_id"]
                result = await client.get_optimization_jobs(kb_id)
                
                jobs = result.get('jobs', [])
                response = f"# 优化任务列表\n\n"
                response += f"**知识库ID**: {kb_id}\n"
                response += f"**任务总数**: {len(jobs)}\n\n"
                
                if jobs:
                    for job in jobs:
                        mode_desc = {
                            'shadow': '影子模式',
                            'edit': '编辑模式',
                            'annotate': '标注模式'
                        }.get(job.get('mode', ''), job.get('mode', ''))
                        
                        response += f"## 任务 {job['job_id']}\n"
                        response += f"- **模式**: {mode_desc}\n"
                        response += f"- **状态**: {job['status']}\n"
                        response += f"- **批处理大小**: {job.get('batch_size', 'N/A')}\n"
                        response += f"- **自动应用**: {'是' if job.get('auto_apply') else '否'}\n"
                        response += f"- **创建时间**: {job['created_at']}\n"
                        response += f"- **更新时间**: {job['updated_at']}\n"
                        if job.get('error_message'):
                            response += f"- **错误信息**: {job['error_message']}\n"
                        response += "\n"
                else:
                    response += "暂无优化任务。"
                
                return [types.TextContent(type="text", text=response)]
                
            elif name == "get_optimization_job_status":
                kb_id = arguments["kb_id"]
                job_id = arguments["job_id"]
                result = await client.get_optimization_job_status(kb_id, job_id)
                
                mode_desc = {
                    'shadow': '影子模式',
                    'edit': '编辑模式',
                    'annotate': '标注模式'
                }.get(result.get('mode', ''), result.get('mode', ''))
                
                response = f"# 优化任务状态\n\n"
                response += f"**任务ID**: {result['job_id']}\n"
                response += f"**知识库ID**: {result['kb_id']}\n"
                response += f"**模式**: {mode_desc}\n"
                response += f"**状态**: {result['status']}\n"
                response += f"**批处理大小**: {result.get('batch_size', 'N/A')}\n"
                response += f"**自动应用**: {'是' if result.get('auto_apply') else '否'}\n"
                response += f"**创建时间**: {result['created_at']}\n"
                response += f"**更新时间**: {result['updated_at']}\n"
                
                if result.get('error_message'):
                    response += f"**错误信息**: {result['error_message']}\n"
                
                # 显示结果（如果有）
                if result.get('result'):
                    response += f"\n## 任务结果\n\n"
                    task_result = result['result']
                    if isinstance(task_result, dict):
                        if task_result.get('operations'):
                            response += f"- **执行的操作数**: {len(task_result['operations'])}\n"
                        if task_result.get('annotations'):
                            response += f"- **生成的标注数**: {len(task_result['annotations'])}\n"
                        if task_result.get('reasoning'):
                            response += f"- **推理过程**: {task_result['reasoning'][:200]}...\n"
                
                return [types.TextContent(type="text", text=response)]
                
            elif name == "get_tagging_overview":
                kb_id = arguments["kb_id"]
                stats_result = await client.get_tagging_stats(kb_id)
                untagged_result = await client.get_untagged_chunks(kb_id, 5)  # 获取少量样本
                
                response = f"# 标签管理概览\n\n"
                response += f"**知识库ID**: {kb_id}\n\n"
                
                # 标注统计
                response += f"## 📈 标注统计\n\n"
                response += f"{json.dumps(stats_result, ensure_ascii=False, indent=2)}\n\n"
                
                # 未标注内容
                response += f"## 📝 未标注内容\n\n"
                response += f"**未标注片段总数**: {untagged_result.get('total_untagged', 0)}\n"
                
                chunks = untagged_result.get('chunks', [])
                if chunks:
                    response += f"**样本片段** (显示前5个):\n\n"
                    for i, chunk in enumerate(chunks, 1):
                        response += f"### 片段 {i}\n"
                        response += f"**片段ID**: {chunk['id']}\n"
                        response += f"**文档ID**: {chunk['document_id']}\n"
                        response += f"**内容**: {chunk['content']}\n\n"
                else:
                    response += "✅ 所有片段都已标注！\n"
                
                return [types.TextContent(type="text", text=response)]
                
            elif name == "get_untagged_content":
                kb_id = arguments["kb_id"]
                limit = arguments.get("limit", 10)
                result = await client.get_untagged_chunks(kb_id, limit)
                
                response = f"# 未标注内容\n\n"
                response += f"**知识库ID**: {kb_id}\n"
                response += f"**未标注片段总数**: {result.get('total_untagged', 0)}\n"
                response += f"**显示数量**: {limit}\n\n"
                
                chunks = result.get('chunks', [])
                if chunks:
                    for i, chunk in enumerate(chunks, 1):
                        response += f"## 片段 {i}\n"
                        response += f"**片段ID**: {chunk['id']}\n"
                        response += f"**文档ID**: {chunk['document_id']}\n"
                        response += f"**片段索引**: {chunk['chunk_index']}\n"
                        response += f"**内容**: {chunk['content']}\n\n"
                else:
                    response += "✅ 所有片段都已标注！\n"
                
                return [types.TextContent(type="text", text=response)]
                
            elif name == "start_smart_tagging":
                kb_id = arguments["kb_id"]
                document_id = arguments.get("document_id")
                chunk_ids = arguments.get("chunk_ids")
                
                result = await client.start_tagging_task(kb_id, document_id, chunk_ids)
                
                response = f"# 智能标注任务\n\n"
                response += f"**知识库ID**: {kb_id}\n"
                
                if document_id:
                    response += f"**标注目标**: 文档 {document_id}\n"
                elif chunk_ids:
                    response += f"**标注目标**: {len(chunk_ids)} 个指定片段\n"
                else:
                    response += f"**标注目标**: 所有未标注片段\n"
                
                response += f"**任务状态**: {result.get('success', False)}\n"
                response += f"**处理结果**: {result.get('message', 'N/A')}\n\n"
                
                # 显示标注结果
                if result.get('tagged_chunks'):
                    response += f"## 标注结果\n\n"
                    for chunk_result in result['tagged_chunks'][:5]:  # 限制显示数量
                        response += f"- **片段 {chunk_result['chunk_id']}**: {', '.join(chunk_result.get('tags', []))}\n"
                
                return [types.TextContent(type="text", text=response)]
                
            elif name == "get_document_visual_preview":
                document_id = arguments["document_id"]
                result = await client.get_document_screenshots(document_id)
                
                data = result.get('data', {})
                screenshots = data.get('screenshots', [])
                
                response = f"# 文档可视化预览\n\n"
                response += f"**文档ID**: {document_id}\n"
                response += f"**总页数**: {data.get('total_pages', 0)}\n\n"
                
                if screenshots:
                    response += f"## 页面截图\n\n"
                    for screenshot in screenshots:
                        response += f"### 第 {screenshot['page_number']} 页\n"
                        response += f"**截图ID**: {screenshot['id']}\n"
                        response += f"**尺寸**: {screenshot['width']} × {screenshot['height']}\n"
                        response += f"**创建时间**: {screenshot.get('created_at', 'N/A')}\n\n"
                        response += f"💡 使用 `get_screenshot_details` 工具查看详细信息。\n\n"
                else:
                    response += "📄 该文档暂无可视化预览。\n"
                
                return [types.TextContent(type="text", text=response)]
                
            elif name == "get_screenshot_details":
                screenshot_id = arguments["screenshot_id"]
                result = await client.get_screenshot_info(screenshot_id)
                
                data = result.get('data', {})
                response = f"# 截图详细信息\n\n"
                response += f"**截图ID**: {screenshot_id}\n"
                response += f"**页码**: {data.get('page_number', 'N/A')}\n"
                response += f"**尺寸**: {data.get('width', 'N/A')} × {data.get('height', 'N/A')}\n"
                response += f"**创建时间**: {data.get('created_at', 'N/A')}\n\n"
                response += f"💡 截图文件可通过 `/screenshots/{screenshot_id}/image` 端点访问。\n"
                
                return [types.TextContent(type="text", text=response)]
                
            else:
                raise ValueError(f"未知工具: {name}")
                
    except Exception as e:
        error_message = f"❌ 错误: {str(e)}{auth_warning}"
        
        # 为认证相关错误提供额外提示
        if "403" in str(e) or "401" in str(e) or "未授权" in str(e) or "禁止访问" in str(e):
            error_message += "\n\n💡 解决方案:\n1. 确保在.env文件中配置了正确的KOSMOS_USERNAME和KOSMOS_PASSWORD\n2. 检查用户是否有访问该知识库的权限\n3. 确认知识库是否为公开状态"
        
        return [types.TextContent(
            type="text",
            text=error_message
        )]

async def main():
    """主函数"""
    # 获取环境变量
    base_url = os.getenv('KOSMOS_BASE_URL')
    if not base_url:
        print("错误: 请在.env文件中配置KOSMOS_BASE_URL")
        return
    
    # 运行服务器
    from mcp.server.stdio import stdio_server
    
    async with stdio_server() as streams:
        await server.run(
            streams[0], 
            streams[1], 
            InitializationOptions(
                server_name="kosmos-knowledge-base",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                )
            )
        )

if __name__ == "__main__":
    asyncio.run(main())