"""
Kosmos知识库MCP Server
提供Kosmos知识库功能的MCP接口
"""

import asyncio
import logging
import os
from typing import Any, Sequence

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.server.lowlevel import NotificationOptions
from mcp.types import (
    Resource, Tool, TextContent, ImageContent, EmbeddedResource,
    CallToolRequest, ReadResourceRequest, ListResourcesRequest, ListToolsRequest
)

from core import KosmosClient, KosmosMCPTools, ToolHandler

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KosmosMCPServer:
    """Kosmos MCP Server"""

    def __init__(self):
        self.server = Server("kosmos-knowledge-base")
        self.kosmos_client = None
        self.tool_handler = None

        # 从环境变量获取配置
        self.base_url = os.getenv("KOSMOS_BASE_URL", "http://localhost:8000")
        self.username = os.getenv("KOSMOS_USERNAME")
        self.password = os.getenv("KOSMOS_PASSWORD")

        if not self.username or not self.password:
            raise ValueError("请设置KOSMOS_USERNAME和KOSMOS_PASSWORD环境变量")

        # 注册处理器
        self._register_handlers()

    def _register_handlers(self):
        """注册MCP处理器"""

        @self.server.list_resources()
        async def handle_list_resources() -> list[Resource]:
            """列出可用资源"""
            return [
                Resource(
                    uri="kosmos://knowledge-bases",
                    name="Kosmos知识库",
                    description="访问Kosmos知识库系统",
                    mimeType="application/json"
                )
            ]

        @self.server.read_resource()
        async def handle_read_resource(uri: str) -> str:
            """获取资源内容"""
            if uri == "kosmos://knowledge-bases":
                if not self.kosmos_client:
                    await self._ensure_authenticated()

                result = await self.kosmos_client.request("GET", "/api/v1/kbs/")
                if "error" in result:
                    return f"获取知识库列表失败: {result['error']}"

                return f"Kosmos知识库系统包含 {len(result)} 个知识库"

            raise ValueError(f"未知资源: {uri}")

        @self.server.list_tools()
        async def handle_list_tools() -> list[Tool]:
            """列出可用工具"""
            return KosmosMCPTools.get_tools()

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            """处理工具调用"""
            if not self.tool_handler:
                await self._ensure_authenticated()

            return await self.tool_handler.handle_tool_call(name, arguments)

    async def _ensure_authenticated(self):
        """确保已认证"""
        if not self.kosmos_client:
            self.kosmos_client = KosmosClient(self.base_url, self.username, self.password)

        if not self.kosmos_client.token:
            success = await self.kosmos_client.authenticate()
            if not success:
                raise RuntimeError("Kosmos认证失败")

        if not self.tool_handler:
            self.tool_handler = ToolHandler(self.kosmos_client)

    async def run(self):
        """运行MCP Server"""
        logger.info(f"启动Kosmos MCP Server，连接到: {self.base_url}")

        # 初始认证
        await self._ensure_authenticated()
        logger.info("Kosmos认证成功")

        # 运行服务器
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="kosmos-knowledge-base",
                    server_version="2.0.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(
                            resources_changed=False,
                            tools_changed=False,
                            prompts_changed=False
                        ),
                        experimental_capabilities={}
                    ),
                ),
            )


async def main():
    """主函数"""
    try:
        server = KosmosMCPServer()
        await server.run()
    except KeyboardInterrupt:
        logger.info("服务器已停止")
    except Exception as e:
        logger.error(f"服务器错误: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(main())