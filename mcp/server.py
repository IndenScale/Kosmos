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