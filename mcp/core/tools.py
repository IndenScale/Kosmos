"""
MCP工具定义
将Kosmos的核心功能封装为MCP工具
"""

from typing import List, Dict, Any, Optional
from mcp.types import Tool, TextContent
import json


class KosmosMCPTools:
    """Kosmos MCP工具集合"""
    
    @staticmethod
    def get_tools() -> List[Tool]:
        """获取所有可用的MCP工具"""
        return [
            # 知识库管理
            Tool(
                name="list_knowledge_bases",
                description="列出用户可访问的知识库",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            
            Tool(
                name="get_knowledge_base",
                description="获取知识库详细信息",
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
                name="create_knowledge_base",
                description="创建新的知识库",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "知识库名称"
                        },
                        "description": {
                            "type": "string",
                            "description": "知识库描述"
                        },
                        "is_public": {
                            "type": "boolean",
                            "description": "是否公开",
                            "default": False
                        }
                    },
                    "required": ["name"]
                }
            ),
            
            # 文档管理
            Tool(
                name="list_documents",
                description="列出知识库中的文档",
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
                name="get_document",
                description="获取文档详细信息",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "kb_id": {
                            "type": "string",
                            "description": "知识库ID"
                        },
                        "document_id": {
                            "type": "string",
                            "description": "文档ID"
                        }
                    },
                    "required": ["kb_id", "document_id"]
                }
            ),
            
            # 搜索功能
            Tool(
                name="search_knowledge_base",
                description="在知识库中进行语义搜索",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "kb_id": {
                            "type": "string",
                            "description": "知识库ID"
                        },
                        "query": {
                            "type": "string",
                            "description": "搜索查询，支持标签语法：+tag（必须有）、-tag（必须没有）、~tag（偏好）"
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "返回结果数量",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 50
                        },
                        "fragment_types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Fragment类型过滤（text, image, table, code等）",
                            "default": ["text"]
                        },
                        "must_tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "必须包含的标签",
                            "default": []
                        },
                        "must_not_tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "必须不包含的标签",
                            "default": []
                        },
                        "like_tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "偏好标签",
                            "default": []
                        }
                    },
                    "required": ["kb_id", "query"]
                }
            ),
            
            Tool(
                name="get_fragment",
                description="获取Fragment详细信息",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "fragment_id": {
                            "type": "string",
                            "description": "Fragment ID"
                        },
                        "kb_id": {
                            "type": "string",
                            "description": "知识库ID（可选，用于权限验证）"
                        }
                    },
                    "required": ["fragment_id"]
                }
            ),
            
            # 解析功能
            Tool(
                name="parse_document",
                description="解析文档生成Fragment",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "kb_id": {
                            "type": "string",
                            "description": "知识库ID"
                        },
                        "document_id": {
                            "type": "string",
                            "description": "文档ID"
                        },
                        "force_reparse": {
                            "type": "boolean",
                            "description": "是否强制重新解析",
                            "default": False
                        }
                    },
                    "required": ["kb_id", "document_id"]
                }
            ),
            
            # 任务管理
            Tool(
                name="list_jobs",
                description="列出任务",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "kb_id": {
                            "type": "string",
                            "description": "知识库ID（可选）"
                        },
                        "job_type": {
                            "type": "string",
                            "description": "任务类型（可选）"
                        },
                        "status": {
                            "type": "string",
                            "description": "任务状态（可选）"
                        },
                        "page": {
                            "type": "integer",
                            "description": "页码",
                            "default": 1,
                            "minimum": 1
                        },
                        "page_size": {
                            "type": "integer",
                            "description": "每页数量",
                            "default": 20,
                            "minimum": 1,
                            "maximum": 100
                        }
                    },
                    "required": []
                }
            ),
            
            Tool(
                name="get_job",
                description="获取任务详情",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "job_id": {
                            "type": "string",
                            "description": "任务ID"
                        }
                    },
                    "required": ["job_id"]
                }
            ),
            
            # 统计信息
            Tool(
                name="get_kb_stats",
                description="获取知识库统计信息",
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
                name="get_fragment_types",
                description="获取知识库中可用的Fragment类型",
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
            
            # 文件上传功能
            Tool(
                name="upload_file",
                description="上传单个文件到知识库",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "kb_id": {
                            "type": "string",
                            "description": "知识库ID"
                        },
                        "file_path": {
                            "type": "string",
                            "description": "本地文件路径"
                        },
                        "auto_parse": {
                            "type": "boolean",
                            "description": "上传后是否自动解析",
                            "default": True
                        }
                    },
                    "required": ["kb_id", "file_path"]
                }
            ),
            
            Tool(
                name="upload_directory",
                description="上传目录中的所有支持文件到知识库",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "kb_id": {
                            "type": "string",
                            "description": "知识库ID"
                        },
                        "directory_path": {
                            "type": "string",
                            "description": "本地目录路径"
                        },
                        "recursive": {
                            "type": "boolean",
                            "description": "是否递归上传子目录",
                            "default": True
                        },
                        "auto_parse": {
                            "type": "boolean",
                            "description": "上传后是否自动解析",
                            "default": True
                        },
                        "file_extensions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "限制上传的文件扩展名（如['.pdf', '.docx']），为空则上传所有支持的文件",
                            "default": []
                        }
                    },
                    "required": ["kb_id", "directory_path"]
                }
            ),
            
            # 标签字典管理
            Tool(
                name="get_tag_dictionary",
                description="获取知识库的标签字典配置",
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
                name="update_tag_dictionary",
                description="更新知识库的标签字典配置（警告：此操作影响重大，会影响所有后续的文档解析和索引生成）",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "kb_id": {
                            "type": "string",
                            "description": "知识库ID"
                        },
                        "tag_dictionary": {
                            "type": "object",
                            "description": "标签字典JSON对象，格式为 {\"标签名\": \"标签描述\", \"分类\": {\"子标签\": \"描述\"}}",
                            "additionalProperties": True
                        }
                    },
                    "required": ["kb_id", "tag_dictionary"]
                }
            ),
            
            # 解析和索引流程
            Tool(
                name="start_kb_parse",
                description="启动知识库的批量解析流程",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "kb_id": {
                            "type": "string",
                            "description": "知识库ID"
                        },
                        "force_reparse": {
                            "type": "boolean",
                            "description": "是否强制重新解析已解析的文档",
                            "default": False
                        },
                        "document_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "指定要解析的文档ID列表，为空则解析所有文档",
                            "default": []
                        }
                    },
                    "required": ["kb_id"]
                }
            ),
            
            Tool(
                name="start_kb_index",
                description="启动知识库的批量索引流程",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "kb_id": {
                            "type": "string",
                            "description": "知识库ID"
                        },
                        "force_reindex": {
                            "type": "boolean",
                            "description": "是否强制重新索引已索引的Fragment",
                            "default": False
                        },
                        "fragment_types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "指定要索引的Fragment类型，为空则索引所有类型",
                            "default": []
                        }
                    },
                    "required": ["kb_id"]
                }
            ),
            
            # 文档就绪状态
            Tool(
                name="get_kb_readiness_status",
                description="获取知识库文档就绪状态（文档是否都有fragment，text_fragment是否都有index）",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "kb_id": {
                            "type": "string",
                            "description": "知识库ID"
                        },
                        "detailed": {
                            "type": "boolean",
                            "description": "是否返回详细的文档级别状态",
                            "default": False
                        }
                    },
                    "required": ["kb_id"]
                }
            ),
            
            Tool(
                name="get_document_readiness_status",
                description="获取单个文档的就绪状态",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "kb_id": {
                            "type": "string",
                            "description": "知识库ID"
                        },
                        "document_id": {
                            "type": "string",
                            "description": "文档ID"
                        }
                    },
                    "required": ["kb_id", "document_id"]
                }
            )
        ]