"""
响应格式化器
将Kosmos API响应格式化为简洁的MCP响应
"""

from typing import Dict, Any, List
import json
from datetime import datetime


class ResponseFormatter:
    """响应格式化器"""
    
    def format_knowledge_bases(self, kbs: List[Dict[str, Any]]) -> str:
        """格式化知识库列表"""
        if not kbs:
            return "没有找到知识库。"
        
        result = f"找到 {len(kbs)} 个知识库:\n\n"
        for kb in kbs:
            result += f"• **{kb['name']}** (ID: {kb['id']})\n"
            if kb.get('description'):
                result += f"  描述: {kb['description']}\n"
            result += f"  公开: {'是' if kb.get('is_public') else '否'}\n"
            result += f"  创建时间: {self._format_datetime(kb.get('created_at'))}\n\n"
        
        return result.strip()
    
    def format_knowledge_base_detail(self, kb: Dict[str, Any]) -> str:
        """格式化知识库详情"""
        result = f"**知识库详情**\n\n"
        result += f"名称: {kb['name']}\n"
        result += f"ID: {kb['id']}\n"
        if kb.get('description'):
            result += f"描述: {kb['description']}\n"
        result += f"所有者: {kb.get('owner_username', '未知')}\n"
        result += f"公开: {'是' if kb.get('is_public') else '否'}\n"
        result += f"创建时间: {self._format_datetime(kb.get('created_at'))}\n"
        
        # 成员信息
        members = kb.get('members', [])
        if members:
            result += f"\n**成员 ({len(members)} 人):**\n"
            for member in members:
                result += f"• {member['username']} ({member['role']})\n"
        
        # 标签字典
        tag_dict = kb.get('tag_dictionary', {})
        if tag_dict:
            result += f"\n**标签字典 ({len(tag_dict)} 个标签):**\n"
            for tag, desc in tag_dict.items():
                result += f"• {tag}: {desc}\n"
        
        return result
    
    def format_knowledge_base_created(self, kb: Dict[str, Any]) -> str:
        """格式化知识库创建结果"""
        return f"✅ 知识库创建成功!\n\n名称: {kb['name']}\nID: {kb['id']}\n创建时间: {self._format_datetime(kb.get('created_at'))}"
    
    def format_documents(self, docs_data: Dict[str, Any]) -> str:
        """格式化文档列表"""
        documents = docs_data.get('documents', [])
        total = docs_data.get('total', len(documents))
        
        if not documents:
            return "该知识库中没有文档。"
        
        result = f"找到 {total} 个文档:\n\n"
        for doc in documents:
            doc_info = doc.get('document', {})
            result += f"• **{doc_info.get('filename', '未知文件')}**\n"
            result += f"  ID: {doc_info.get('id')}\n"
            result += f"  类型: {doc_info.get('file_type', '未知')}\n"
            result += f"  大小: {self._format_file_size(doc_info.get('file_size', 0))}\n"
            result += f"  上传时间: {self._format_datetime(doc.get('upload_at'))}\n"
            if doc.get('chunk_count'):
                result += f"  片段数: {doc['chunk_count']}\n"
            result += "\n"
        
        return result.strip()
    
    def format_document_detail(self, doc: Dict[str, Any]) -> str:
        """格式化文档详情"""
        doc_info = doc.get('document', {})
        result = f"**文档详情**\n\n"
        result += f"文件名: {doc_info.get('filename', '未知文件')}\n"
        result += f"文档ID: {doc_info.get('id')}\n"
        result += f"文件类型: {doc_info.get('file_type', '未知')}\n"
        result += f"文件大小: {self._format_file_size(doc_info.get('file_size', 0))}\n"
        result += f"上传时间: {self._format_datetime(doc.get('upload_at'))}\n"
        if doc.get('last_ingest_time'):
            result += f"最后处理时间: {self._format_datetime(doc['last_ingest_time'])}\n"
        if doc.get('chunk_count'):
            result += f"片段数量: {doc['chunk_count']}\n"
        if doc.get('uploader_username'):
            result += f"上传者: {doc['uploader_username']}\n"
        
        return result
    
    def format_search_results(self, results: Dict[str, Any]) -> str:
        """格式化搜索结果"""
        fragments = results.get('results', [])
        query_parse_result = results.get('query_parse_result', {})
        stats = results.get('stats', {})
        
        if not fragments:
            return "没有找到相关内容。"
        
        result = f"**搜索结果** (找到 {len(fragments)} 个相关片段)\n\n"
        
        # 查询信息
        if query_parse_result:
            result += f"查询: {query_parse_result.get('original_query', '')}\n"
            if query_parse_result.get('must_tags'):
                result += f"必须标签: {', '.join(query_parse_result['must_tags'])}\n"
            if query_parse_result.get('must_not_tags'):
                result += f"排除标签: {', '.join(query_parse_result['must_not_tags'])}\n"
            if query_parse_result.get('like_tags'):
                result += f"偏好标签: {', '.join(query_parse_result['like_tags'])}\n"
            result += "\n"
        
        # 统计信息
        if stats:
            result += f"搜索统计: 原始结果 {stats.get('original_count', 0)} 个，去重后 {stats.get('deduplicated_count', 0)} 个，最终返回 {stats.get('final_count', 0)} 个\n"
            if stats.get('search_time_ms'):
                result += f"搜索耗时: {stats['search_time_ms']:.1f}ms\n"
            result += "\n"
        
        # 搜索结果
        for i, fragment in enumerate(fragments, 1):
            result += f"**{i}. {fragment.get('source_file_name', '未知文档')}**\n"
            result += f"相似度: {fragment.get('score', 0):.3f}\n"
            result += f"类型: {fragment.get('fragment_type', '未知')}\n"
            
            # 标签
            tags = fragment.get('tags', [])
            if tags:
                result += f"标签: {', '.join(tags)}\n"
            
            # 页面范围
            meta_info = fragment.get('meta_info', {})
            if meta_info.get('page_start') and meta_info.get('page_end'):
                result += f"页面: {meta_info['page_start']}-{meta_info['page_end']}\n"
            
            # 内容预览
            content = fragment.get('content', '')
            if content:
                preview = content[:300] + "..." if len(content) > 300 else content
                result += f"内容: {preview}\n"
            
            result += f"Fragment ID: {fragment.get('fragment_id')}\n\n"
        
        # 推荐标签
        recommended_tags = results.get('recommended_tags', [])
        if recommended_tags:
            result += "**推荐标签:**\n"
            for tag_info in recommended_tags[:5]:  # 只显示前5个
                result += f"• {tag_info['tag']} (相关度: {tag_info['relevance']}, 数量: {tag_info['count']})\n"
        
        return result.strip()
    
    def format_fragment_detail(self, fragment: Dict[str, Any]) -> str:
        """格式化Fragment详情"""
        result = f"**Fragment详情**\n\n"
        result += f"ID: {fragment.get('id')}\n"
        result += f"类型: {fragment.get('fragment_type', '未知')}\n"
        result += f"文档: {fragment.get('document_filename', '未知文档')}\n"
        
        # 标签
        tags = fragment.get('tags', [])
        if tags:
            result += f"标签: {', '.join(tags)}\n"
        
        # 位置信息
        if fragment.get('page_number'):
            result += f"页码: {fragment['page_number']}\n"
        if fragment.get('bbox'):
            bbox = fragment['bbox']
            result += f"位置: ({bbox[0]:.1f}, {bbox[1]:.1f}, {bbox[2]:.1f}, {bbox[3]:.1f})\n"
        
        # 内容
        content = fragment.get('content', '')
        if content:
            result += f"\n**内容:**\n{content}\n"
        
        return result
    
    def format_parse_result(self, result: Dict[str, Any]) -> str:
        """格式化解析结果"""
        if not result.get('success'):
            return f"❌ 解析失败: {result.get('error_message', '未知错误')}"
        
        response = f"✅ 文档解析成功!\n\n"
        response += f"文档ID: {result.get('document_id')}\n"
        response += f"总片段数: {result.get('total_fragments', 0)}\n"
        response += f"文本片段: {result.get('text_fragments', 0)}\n"
        response += f"截图片段: {result.get('screenshot_fragments', 0)}\n"
        response += f"图表片段: {result.get('figure_fragments', 0)}\n"
        
        if result.get('parse_duration_ms'):
            response += f"解析耗时: {result['parse_duration_ms']}ms\n"
        
        return response
    
    def format_jobs(self, jobs_data: Dict[str, Any]) -> str:
        """格式化任务列表"""
        jobs = jobs_data.get('jobs', [])
        total = jobs_data.get('total', len(jobs))
        
        if not jobs:
            return "没有找到任务。"
        
        result = f"找到 {total} 个任务:\n\n"
        for job in jobs:
            result += f"• **{job.get('job_type', '未知类型')}** (ID: {job.get('id')})\n"
            result += f"  状态: {job.get('status', '未知')}\n"
            result += f"  进度: {job.get('progress_percentage', 0):.1f}%\n"
            result += f"  创建时间: {self._format_datetime(job.get('created_at'))}\n"
            if job.get('kb_id'):
                result += f"  知识库: {job['kb_id']}\n"
            result += "\n"
        
        return result.strip()
    
    def format_job_detail(self, job: Dict[str, Any]) -> str:
        """格式化任务详情"""
        result = f"**任务详情**\n\n"
        result += f"ID: {job.get('id')}\n"
        result += f"类型: {job.get('job_type', '未知')}\n"
        result += f"状态: {job.get('status', '未知')}\n"
        result += f"进度: {job.get('progress_percentage', 0):.1f}%\n"
        result += f"总任务数: {job.get('total_tasks', 0)}\n"
        result += f"已完成: {job.get('completed_tasks', 0)}\n"
        result += f"失败数: {job.get('failed_tasks', 0)}\n"
        result += f"创建时间: {self._format_datetime(job.get('created_at'))}\n"
        
        if job.get('started_at'):
            result += f"开始时间: {self._format_datetime(job['started_at'])}\n"
        if job.get('completed_at'):
            result += f"完成时间: {self._format_datetime(job['completed_at'])}\n"
        if job.get('error_message'):
            result += f"错误信息: {job['error_message']}\n"
        if job.get('kb_id'):
            result += f"知识库: {job['kb_id']}\n"
        
        return result
    
    def format_kb_stats(self, stats: Dict[str, Any]) -> str:
        """格式化知识库统计"""
        result = f"**知识库统计信息**\n\n"
        result += f"总片段数: {stats.get('total_fragments', 0)}\n"
        result += f"文本片段: {stats.get('text_fragments', 0)}\n"
        result += f"图像片段: {stats.get('image_fragments', 0)}\n"
        result += f"表格片段: {stats.get('table_fragments', 0)}\n"
        result += f"代码片段: {stats.get('code_fragments', 0)}\n"
        result += f"其他片段: {stats.get('other_fragments', 0)}\n"
        
        if stats.get('avg_content_length'):
            result += f"平均内容长度: {stats['avg_content_length']:.1f} 字符\n"
        
        return result
    
    def format_fragment_types(self, types: List[str]) -> str:
        """格式化Fragment类型"""
        if not types:
            return "该知识库中没有Fragment类型。"
        
        return f"可用的Fragment类型 ({len(types)} 种):\n" + "\n".join(f"• {t}" for t in types)
    
    # 文件上传相关格式化
    def format_upload_result(self, result: Dict[str, Any], filename: str) -> str:
        """格式化文件上传结果"""
        if result.get('success'):
            response = f"✅ 文件上传成功!\n\n"
            response += f"文件名: {filename}\n"
            response += f"文档ID: {result.get('document_id')}\n"
            if result.get('auto_parse'):
                response += f"自动解析: 已启动\n"
            return response
        else:
            return f"❌ 文件上传失败: {result.get('error_message', '未知错误')}"
    
    # 标签字典相关格式化
    def format_tag_dictionary(self, tag_dict: Dict[str, Any]) -> str:
        """格式化标签字典"""
        if not tag_dict:
            return "该知识库没有配置标签字典。"
        
        result = f"**标签字典** ({len(tag_dict)} 个标签):\n\n"
        for tag, desc in tag_dict.items():
            if isinstance(desc, dict):
                result += f"**{tag}** (分类):\n"
                for sub_tag, sub_desc in desc.items():
                    result += f"  • {sub_tag}: {sub_desc}\n"
            else:
                result += f"• **{tag}**: {desc}\n"
        
        return result.strip()
    
    def format_tag_dictionary_updated(self, result: Dict[str, Any]) -> str:
        """格式化标签字典更新结果"""
        if result.get('success'):
            return "✅ 标签字典更新成功!\n\n⚠️ 警告: 标签字典的更改会影响所有后续的文档解析和索引生成。建议重新解析和索引相关文档以确保一致性。"
        else:
            return f"❌ 标签字典更新失败: {result.get('error_message', '未知错误')}"
    
    # 解析和索引相关格式化
    def format_parse_job_started(self, result: Dict[str, Any]) -> str:
        """格式化解析任务启动结果"""
        if result.get('success'):
            response = f"✅ 知识库解析任务已启动!\n\n"
            response += f"任务ID: {result.get('job_id')}\n"
            response += f"知识库ID: {result.get('kb_id')}\n"
            if result.get('document_count'):
                response += f"待解析文档数: {result['document_count']}\n"
            response += f"状态: {result.get('status', '运行中')}\n"
            return response
        else:
            return f"❌ 启动解析任务失败: {result.get('error_message', '未知错误')}"
    
    def format_index_job_started(self, result: Dict[str, Any]) -> str:
        """格式化索引任务启动结果"""
        if result.get('success'):
            response = f"✅ 知识库索引任务已启动!\n\n"
            response += f"任务ID: {result.get('job_id')}\n"
            response += f"知识库ID: {result.get('kb_id')}\n"
            if result.get('fragment_count'):
                response += f"待索引Fragment数: {result['fragment_count']}\n"
            response += f"状态: {result.get('status', '运行中')}\n"
            return response
        else:
            return f"❌ 启动索引任务失败: {result.get('error_message', '未知错误')}"
    
    # 文档就绪状态相关格式化
    def format_kb_readiness_status(self, stats: Dict[str, Any], docs: Dict[str, Any]) -> str:
        """格式化知识库就绪状态"""
        documents = docs.get('documents', [])
        total_docs = len(documents)
        
        # 统计信息
        total_fragments = stats.get('total_fragments', 0)
        text_fragments = stats.get('text_fragments', 0)
        indexed_fragments = stats.get('indexed_fragments', 0)
        
        result = f"**知识库就绪状态**\n\n"
        result += f"📄 文档总数: {total_docs}\n"
        result += f"🧩 总Fragment数: {total_fragments}\n"
        result += f"📝 文本Fragment数: {text_fragments}\n"
        result += f"🔍 已索引Fragment数: {indexed_fragments}\n\n"
        
        # 就绪状态评估
        if total_docs == 0:
            result += "⚠️ 状态: 无文档\n"
        elif total_fragments == 0:
            result += "⚠️ 状态: 文档未解析\n建议: 启动解析流程\n"
        elif text_fragments > 0 and indexed_fragments == 0:
            result += "⚠️ 状态: Fragment未索引\n建议: 启动索引流程\n"
        elif indexed_fragments < text_fragments:
            index_rate = (indexed_fragments / text_fragments) * 100
            result += f"🔄 状态: 部分索引完成 ({index_rate:.1f}%)\n建议: 等待索引完成或重新启动索引\n"
        else:
            result += "✅ 状态: 完全就绪\n所有文档已解析且文本Fragment已索引\n"
        
        return result
    
    def format_detailed_readiness_status(self, stats: Dict[str, Any], docs: Dict[str, Any], doc_statuses: List[Dict[str, Any]]) -> str:
        """格式化详细就绪状态"""
        result = self.format_kb_readiness_status(stats, docs)
        result += "\n\n**文档详细状态:**\n\n"
        
        for doc_status in doc_statuses:
            doc = doc_status['document']
            doc_stats = doc_status['stats']
            
            doc_fragments = doc_stats.get('total_fragments', 0)
            doc_text_fragments = doc_stats.get('text_fragments', 0)
            doc_indexed = doc_stats.get('indexed_fragments', 0)
            
            result += f"• **{doc.get('filename', '未知文件')}**\n"
            result += f"  Fragment数: {doc_fragments}\n"
            result += f"  文本Fragment: {doc_text_fragments}\n"
            result += f"  已索引: {doc_indexed}\n"
            
            if doc_fragments == 0:
                result += f"  状态: ⚠️ 未解析\n"
            elif doc_text_fragments > 0 and doc_indexed == 0:
                result += f"  状态: ⚠️ 未索引\n"
            elif doc_indexed < doc_text_fragments:
                result += f"  状态: 🔄 部分索引\n"
            else:
                result += f"  状态: ✅ 就绪\n"
            result += "\n"
        
        return result.strip()
    
    def format_document_readiness_status(self, doc: Dict[str, Any], stats: Dict[str, Any]) -> str:
        """格式化文档就绪状态"""
        doc_info = doc.get('document', {})
        
        total_fragments = stats.get('total_fragments', 0)
        text_fragments = stats.get('text_fragments', 0)
        indexed_fragments = stats.get('indexed_fragments', 0)
        
        result = f"**文档就绪状态**\n\n"
        result += f"文件名: {doc_info.get('filename', '未知文件')}\n"
        result += f"文档ID: {doc_info.get('id')}\n\n"
        result += f"🧩 总Fragment数: {total_fragments}\n"
        result += f"📝 文本Fragment数: {text_fragments}\n"
        result += f"🔍 已索引Fragment数: {indexed_fragments}\n\n"
        
        # 就绪状态评估
        if total_fragments == 0:
            result += "⚠️ 状态: 未解析\n建议: 启动文档解析\n"
        elif text_fragments > 0 and indexed_fragments == 0:
            result += "⚠️ 状态: 未索引\n建议: 启动索引流程\n"
        elif indexed_fragments < text_fragments:
            index_rate = (indexed_fragments / text_fragments) * 100
            result += f"🔄 状态: 部分索引完成 ({index_rate:.1f}%)\n建议: 等待索引完成\n"
        else:
            result += "✅ 状态: 完全就绪\n文档已解析且文本Fragment已索引\n"
        
        return result
    
    def _format_datetime(self, dt_str: str) -> str:
        """格式化日期时间"""
        if not dt_str:
            return "未知"
        try:
            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            return dt_str
    
    def _format_file_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes == 0:
            return "0 B"
        
        units = ['B', 'KB', 'MB', 'GB']
        size = float(size_bytes)
        unit_index = 0
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        
        return f"{size:.1f} {units[unit_index]}"