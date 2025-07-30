"""
工具处理器
处理MCP工具调用并与Kosmos API交互
"""

from typing import Dict, Any, List, Optional
from mcp.types import TextContent
import json
import logging
from .kosmos_client import KosmosClient
from .response_formatter import ResponseFormatter

logger = logging.getLogger(__name__)


class ToolHandler:
    """MCP工具处理器"""
    
    def __init__(self, kosmos_client: KosmosClient):
        self.client = kosmos_client
        self.formatter = ResponseFormatter()
    
    async def handle_tool_call(self, name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        """处理工具调用"""
        try:
            # 知识库管理
            if name == "list_knowledge_bases":
                return await self._list_knowledge_bases()
            elif name == "get_knowledge_base":
                return await self._get_knowledge_base(arguments["kb_id"])
            elif name == "create_knowledge_base":
                return await self._create_knowledge_base(arguments)
            
            # 文档管理
            elif name == "list_documents":
                return await self._list_documents(arguments["kb_id"])
            elif name == "get_document":
                return await self._get_document(arguments["kb_id"], arguments["document_id"])
            
            # 搜索功能
            elif name == "search_knowledge_base":
                return await self._search_knowledge_base(arguments)
            elif name == "get_fragment":
                return await self._get_fragment(arguments)
            
            # 解析功能
            elif name == "parse_document":
                return await self._parse_document(arguments)
            
            # 任务管理
            elif name == "list_jobs":
                return await self._list_jobs(arguments)
            elif name == "get_job":
                return await self._get_job(arguments["job_id"])
            
            # 统计信息
            elif name == "get_kb_stats":
                return await self._get_kb_stats(arguments["kb_id"])
            elif name == "get_fragment_types":
                return await self._get_fragment_types(arguments["kb_id"])
            
            # 文件上传功能
            elif name == "upload_file":
                return await self._upload_file(arguments)
            elif name == "upload_directory":
                return await self._upload_directory(arguments)
            
            # 标签字典管理
            elif name == "get_tag_dictionary":
                return await self._get_tag_dictionary(arguments["kb_id"])
            elif name == "update_tag_dictionary":
                return await self._update_tag_dictionary(arguments)
            
            # 解析和索引流程
            elif name == "start_kb_parse":
                return await self._start_kb_parse(arguments)
            elif name == "start_kb_index":
                return await self._start_kb_index(arguments)
            
            # 文档就绪状态
            elif name == "get_kb_readiness_status":
                return await self._get_kb_readiness_status(arguments)
            elif name == "get_document_readiness_status":
                return await self._get_document_readiness_status(arguments)
            
            else:
                return [TextContent(type="text", text=f"未知工具: {name}")]
                
        except Exception as e:
            logger.error(f"工具调用失败 {name}: {str(e)}")
            return [TextContent(type="text", text=f"工具调用失败: {str(e)}")]
    
    async def _list_knowledge_bases(self) -> List[TextContent]:
        """列出知识库"""
        result = await self.client.request("GET", "/api/v1/kbs/")
        if "error" in result:
            return [TextContent(type="text", text=f"获取知识库列表失败: {result['error']}")]
        
        formatted = self.formatter.format_knowledge_bases(result)
        return [TextContent(type="text", text=formatted)]
    
    async def _get_knowledge_base(self, kb_id: str) -> List[TextContent]:
        """获取知识库详情"""
        result = await self.client.request("GET", f"/api/v1/kbs/{kb_id}")
        if "error" in result:
            return [TextContent(type="text", text=f"获取知识库详情失败: {result['error']}")]
        
        formatted = self.formatter.format_knowledge_base_detail(result)
        return [TextContent(type="text", text=formatted)]
    
    async def _create_knowledge_base(self, args: Dict[str, Any]) -> List[TextContent]:
        """创建知识库"""
        result = await self.client.request("POST", "/api/v1/kbs/", json=args)
        if "error" in result:
            return [TextContent(type="text", text=f"创建知识库失败: {result['error']}")]
        
        formatted = self.formatter.format_knowledge_base_created(result)
        return [TextContent(type="text", text=formatted)]
    
    async def _list_documents(self, kb_id: str) -> List[TextContent]:
        """列出文档"""
        result = await self.client.request("GET", f"/api/v1/kbs/{kb_id}/documents")
        if "error" in result:
            return [TextContent(type="text", text=f"获取文档列表失败: {result['error']}")]
        
        formatted = self.formatter.format_documents(result)
        return [TextContent(type="text", text=formatted)]
    
    async def _get_document(self, kb_id: str, document_id: str) -> List[TextContent]:
        """获取文档详情"""
        result = await self.client.request("GET", f"/api/v1/kbs/{kb_id}/documents/{document_id}")
        if "error" in result:
            return [TextContent(type="text", text=f"获取文档详情失败: {result['error']}")]
        
        formatted = self.formatter.format_document_detail(result)
        return [TextContent(type="text", text=formatted)]
    
    async def _search_knowledge_base(self, args: Dict[str, Any]) -> List[TextContent]:
        """搜索知识库"""
        kb_id = args.pop("kb_id")
        result = await self.client.request("POST", f"/api/v1/kbs/{kb_id}/search", json=args)
        if "error" in result:
            return [TextContent(type="text", text=f"搜索失败: {result['error']}")]
        
        formatted = self.formatter.format_search_results(result)
        return [TextContent(type="text", text=formatted)]
    
    async def _get_fragment(self, args: Dict[str, Any]) -> List[TextContent]:
        """获取Fragment详情"""
        fragment_id = args["fragment_id"]
        kb_id = args.get("kb_id")
        
        params = {}
        if kb_id:
            params["kb_id"] = kb_id
        
        result = await self.client.request("GET", f"/api/v1/fragments/{fragment_id}", params=params)
        if "error" in result:
            return [TextContent(type="text", text=f"获取Fragment详情失败: {result['error']}")]
        
        formatted = self.formatter.format_fragment_detail(result)
        return [TextContent(type="text", text=formatted)]
    
    async def _parse_document(self, args: Dict[str, Any]) -> List[TextContent]:
        """解析文档"""
        kb_id = args.pop("kb_id")
        result = await self.client.request("POST", f"/api/v1/parser/kb/{kb_id}/parse", json=args)
        if "error" in result:
            return [TextContent(type="text", text=f"解析文档失败: {result['error']}")]
        
        formatted = self.formatter.format_parse_result(result)
        return [TextContent(type="text", text=formatted)]
    
    async def _list_jobs(self, args: Dict[str, Any]) -> List[TextContent]:
        """列出任务"""
        result = await self.client.request("GET", "/api/v1/jobs/", params=args)
        if "error" in result:
            return [TextContent(type="text", text=f"获取任务列表失败: {result['error']}")]
        
        formatted = self.formatter.format_jobs(result)
        return [TextContent(type="text", text=formatted)]
    
    async def _get_job(self, job_id: str) -> List[TextContent]:
        """获取任务详情"""
        result = await self.client.request("GET", f"/api/v1/jobs/{job_id}")
        if "error" in result:
            return [TextContent(type="text", text=f"获取任务详情失败: {result['error']}")]
        
        formatted = self.formatter.format_job_detail(result)
        return [TextContent(type="text", text=formatted)]
    
    async def _get_kb_stats(self, kb_id: str) -> List[TextContent]:
        """获取知识库统计"""
        result = await self.client.request("GET", f"/api/v1/kbs/{kb_id}/fragments/stats")
        if "error" in result:
            return [TextContent(type="text", text=f"获取统计信息失败: {result['error']}")]
        
        formatted = self.formatter.format_kb_stats(result)
        return [TextContent(type="text", text=formatted)]
    
    async def _get_fragment_types(self, kb_id: str) -> List[TextContent]:
        """获取Fragment类型"""
        result = await self.client.request("GET", f"/api/v1/kbs/{kb_id}/search/types")
        if "error" in result:
            return [TextContent(type="text", text=f"获取Fragment类型失败: {result['error']}")]
        
        formatted = self.formatter.format_fragment_types(result)
        return [TextContent(type="text", text=formatted)]
    
    # 文件上传功能
    async def _upload_file(self, args: Dict[str, Any]) -> List[TextContent]:
        """上传单个文件"""
        import os
        import aiofiles
        
        kb_id = args["kb_id"]
        file_path = args["file_path"]
        auto_parse = args.get("auto_parse", True)
        
        if not os.path.exists(file_path):
            return [TextContent(type="text", text=f"文件不存在: {file_path}")]
        
        if not os.path.isfile(file_path):
            return [TextContent(type="text", text=f"路径不是文件: {file_path}")]
        
        try:
            # 读取文件内容
            async with aiofiles.open(file_path, 'rb') as f:
                file_content = await f.read()
            
            # 准备上传数据
            filename = os.path.basename(file_path)
            files = {
                'file': (filename, file_content, 'application/octet-stream')
            }
            data = {
                'auto_parse': str(auto_parse).lower()
            }
            
            # 上传文件
            result = await self.client.request(
                "POST", 
                f"/api/v1/kbs/{kb_id}/documents/upload",
                files=files,
                data=data
            )
            
            if "error" in result:
                return [TextContent(type="text", text=f"文件上传失败: {result['error']}")]
            
            formatted = self.formatter.format_upload_result(result, filename)
            return [TextContent(type="text", text=formatted)]
            
        except Exception as e:
            return [TextContent(type="text", text=f"文件上传异常: {str(e)}")]
    
    async def _upload_directory(self, args: Dict[str, Any]) -> List[TextContent]:
        """上传目录中的所有文件"""
        import os
        import aiofiles
        
        kb_id = args["kb_id"]
        directory_path = args["directory_path"]
        recursive = args.get("recursive", True)
        auto_parse = args.get("auto_parse", True)
        file_extensions = args.get("file_extensions", [])
        
        if not os.path.exists(directory_path):
            return [TextContent(type="text", text=f"目录不存在: {directory_path}")]
        
        if not os.path.isdir(directory_path):
            return [TextContent(type="text", text=f"路径不是目录: {directory_path}")]
        
        # 支持的文件扩展名
        supported_extensions = {'.pdf', '.docx', '.doc', '.txt', '.md', '.html', '.htm', '.rtf', '.odt'}
        
        # 如果指定了文件扩展名，使用指定的，否则使用所有支持的
        target_extensions = set(file_extensions) if file_extensions else supported_extensions
        
        uploaded_files = []
        failed_files = []
        
        try:
            # 遍历目录
            for root, dirs, files in os.walk(directory_path):
                if not recursive and root != directory_path:
                    continue
                
                for file in files:
                    file_path = os.path.join(root, file)
                    file_ext = os.path.splitext(file)[1].lower()
                    
                    if file_ext not in target_extensions:
                        continue
                    
                    try:
                        # 读取文件内容
                        async with aiofiles.open(file_path, 'rb') as f:
                            file_content = await f.read()
                        
                        # 准备上传数据
                        files_data = {
                            'file': (file, file_content, 'application/octet-stream')
                        }
                        data = {
                            'auto_parse': str(auto_parse).lower()
                        }
                        
                        # 上传文件
                        result = await self.client.request(
                            "POST", 
                            f"/api/v1/kbs/{kb_id}/documents/upload",
                            files=files_data,
                            data=data
                        )
                        
                        if "error" in result:
                            failed_files.append(f"{file}: {result['error']}")
                        else:
                            uploaded_files.append(file)
                            
                    except Exception as e:
                        failed_files.append(f"{file}: {str(e)}")
            
            # 格式化结果
            result_text = f"目录上传完成:\n"
            result_text += f"成功上传: {len(uploaded_files)} 个文件\n"
            if uploaded_files:
                result_text += f"上传的文件: {', '.join(uploaded_files[:10])}"
                if len(uploaded_files) > 10:
                    result_text += f" 等 {len(uploaded_files)} 个文件"
                result_text += "\n"
            
            if failed_files:
                result_text += f"失败: {len(failed_files)} 个文件\n"
                result_text += f"失败详情: {'; '.join(failed_files[:5])}"
                if len(failed_files) > 5:
                    result_text += f" 等 {len(failed_files)} 个失败"
            
            return [TextContent(type="text", text=result_text)]
            
        except Exception as e:
            return [TextContent(type="text", text=f"目录上传异常: {str(e)}")]
    
    # 标签字典管理
    async def _get_tag_dictionary(self, kb_id: str) -> List[TextContent]:
        """获取标签字典"""
        result = await self.client.request("GET", f"/api/v1/kbs/{kb_id}")
        if "error" in result:
            return [TextContent(type="text", text=f"获取知识库信息失败: {result['error']}")]
        
        tag_dictionary = result.get("tag_dictionary", {})
        formatted = self.formatter.format_tag_dictionary(tag_dictionary)
        return [TextContent(type="text", text=formatted)]
    
    async def _update_tag_dictionary(self, args: Dict[str, Any]) -> List[TextContent]:
        """更新标签字典"""
        kb_id = args["kb_id"]
        tag_dictionary = args["tag_dictionary"]
        
        data = {"tag_dictionary": tag_dictionary}
        result = await self.client.request("PUT", f"/api/v1/kbs/{kb_id}/tag-dictionary", json=data)
        
        if "error" in result:
            return [TextContent(type="text", text=f"更新标签字典失败: {result['error']}")]
        
        formatted = self.formatter.format_tag_dictionary_updated(result)
        return [TextContent(type="text", text=formatted)]
    
    # 解析和索引流程
    async def _start_kb_parse(self, args: Dict[str, Any]) -> List[TextContent]:
        """启动知识库解析"""
        kb_id = args["kb_id"]
        force_reparse = args.get("force_reparse", False)
        document_ids = args.get("document_ids", [])
        
        data = {
            "force_reparse": force_reparse
        }
        if document_ids:
            data["document_ids"] = document_ids
        
        result = await self.client.request("POST", f"/api/v1/parser/kb/{kb_id}/parse", json=data)
        
        if "error" in result:
            return [TextContent(type="text", text=f"启动解析失败: {result['error']}")]
        
        formatted = self.formatter.format_parse_job_started(result)
        return [TextContent(type="text", text=formatted)]
    
    async def _start_kb_index(self, args: Dict[str, Any]) -> List[TextContent]:
        """启动知识库索引"""
        kb_id = args["kb_id"]
        force_reindex = args.get("force_reindex", False)
        fragment_types = args.get("fragment_types", [])
        
        data = {
            "force_reindex": force_reindex
        }
        if fragment_types:
            data["fragment_types"] = fragment_types
        
        result = await self.client.request("POST", f"/api/v1/indexer/kb/{kb_id}/index", json=data)
        
        if "error" in result:
            return [TextContent(type="text", text=f"启动索引失败: {result['error']}")]
        
        formatted = self.formatter.format_index_job_started(result)
        return [TextContent(type="text", text=formatted)]
    
    # 文档就绪状态
    async def _get_kb_readiness_status(self, args: Dict[str, Any]) -> List[TextContent]:
        """获取知识库就绪状态"""
        kb_id = args["kb_id"]
        detailed = args.get("detailed", False)
        
        # 获取知识库统计信息
        stats_result = await self.client.request("GET", f"/api/v1/kbs/{kb_id}/fragments/stats")
        if "error" in stats_result:
            return [TextContent(type="text", text=f"获取统计信息失败: {stats_result['error']}")]
        
        # 获取文档列表
        docs_result = await self.client.request("GET", f"/api/v1/kbs/{kb_id}/documents")
        if "error" in docs_result:
            return [TextContent(type="text", text=f"获取文档列表失败: {docs_result['error']}")]
        
        if detailed:
            # 获取每个文档的详细状态
            document_statuses = []
            for doc in docs_result.get("documents", []):
                doc_id = doc["id"]
                doc_stats = await self.client.request("GET", f"/api/v1/kbs/{kb_id}/documents/{doc_id}/fragments/stats")
                if "error" not in doc_stats:
                    document_statuses.append({
                        "document": doc,
                        "stats": doc_stats
                    })
            
            formatted = self.formatter.format_detailed_readiness_status(stats_result, docs_result, document_statuses)
        else:
            formatted = self.formatter.format_kb_readiness_status(stats_result, docs_result)
        
        return [TextContent(type="text", text=formatted)]
    
    async def _get_document_readiness_status(self, args: Dict[str, Any]) -> List[TextContent]:
        """获取文档就绪状态"""
        kb_id = args["kb_id"]
        document_id = args["document_id"]
        
        # 获取文档信息
        doc_result = await self.client.request("GET", f"/api/v1/kbs/{kb_id}/documents/{document_id}")
        if "error" in doc_result:
            return [TextContent(type="text", text=f"获取文档信息失败: {doc_result['error']}")]
        
        # 获取文档Fragment统计
        stats_result = await self.client.request("GET", f"/api/v1/kbs/{kb_id}/documents/{document_id}/fragments/stats")
        if "error" in stats_result:
            return [TextContent(type="text", text=f"获取文档统计失败: {stats_result['error']}")]
        
        formatted = self.formatter.format_document_readiness_status(doc_result, stats_result)
        return [TextContent(type="text", text=formatted)]