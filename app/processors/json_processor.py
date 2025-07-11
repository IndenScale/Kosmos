import json
import jsonlines
from typing import Tuple, List, Dict, Any, Union
from pathlib import Path
from .base_processor import BaseProcessor


class JsonProcessor(BaseProcessor):
    """专门处理JSON和JSONL文件的处理器，提供基于JSON对象的智能分割"""
    
    def __init__(self):
        super().__init__()
        self.supported_extensions = ['.json', '.jsonl']
    
    def can_process(self, file_path: str) -> bool:
        """判断是否可以处理该文件类型"""
        file_ext = Path(file_path).suffix.lower()
        return file_ext in self.supported_extensions
    
    def _extract_content_impl(self, file_path: str) -> Tuple[Union[str, List[Dict[str, Any]]], List[str]]:
        """提取JSON/JSONL文档内容"""
        try:
            file_path_obj = Path(file_path)
            file_ext = file_path_obj.suffix.lower()
            
            if file_ext == '.json':
                return self._process_json_file(file_path)
            elif file_ext == '.jsonl':
                return self._process_jsonl_file(file_path)
            else:
                raise Exception(f"不支持的文件类型: {file_ext}")
                
        except Exception as e:
            raise Exception(f"JSON处理器提取内容失败: {str(e)}")
    
    def _process_json_file(self, file_path: str) -> Tuple[str, List[str]]:
        """处理JSON文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 根据JSON结构生成markdown内容
            markdown_content = self._json_to_markdown(data, file_path)
            
            return markdown_content, []
            
        except json.JSONDecodeError as e:
            raise Exception(f"JSON文件解析错误: {str(e)}")
        except Exception as e:
            raise Exception(f"处理JSON文件时发生错误: {str(e)}")
    
    def _process_jsonl_file(self, file_path: str) -> Tuple[List[Dict[str, Any]], List[str]]:
        """处理JSONL文件，返回结构化块列表"""
        try:
            blocks = []
            # Add a header block for context
            blocks.append({
                "type": "heading",
                "level": 1,
                "content": f"JSONL文件: {Path(file_path).name}"
            })
            
            line_number = 0
            
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line_number += 1
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        json_obj = json.loads(line)
                        # 每一行作为一个独立的JSON对象处理
                        obj_markdown = self._json_object_to_markdown(json_obj, f"行 {line_number}")
                        blocks.append({'type': 'text', 'content': obj_markdown})
                    except json.JSONDecodeError:
                        # 如果某行不是有效JSON，以纯文本形式处理
                        plain_text_markdown = f"**行 {line_number} (纯文本):**\n```\n{line}\n```\n"
                        blocks.append({'type': 'text', 'content': plain_text_markdown})
            
            return blocks, []
            
        except Exception as e:
            raise Exception(f"处理JSONL文件时发生错误: {str(e)}")
    
    def _json_to_markdown(self, data: Any, file_path: str, level: int = 1) -> str:
        """将JSON数据转换为markdown格式"""
        markdown_parts = []
        
        # 文件标题
        filename = Path(file_path).name
        markdown_parts.append(f"# JSON文件: {filename}\n")
        
        # 根据数据类型处理
        if isinstance(data, dict):
            markdown_parts.append(self._dict_to_markdown(data, level))
        elif isinstance(data, list):
            markdown_parts.append(self._list_to_markdown(data, level))
        else:
            markdown_parts.append(f"**根级别值:**\n```json\n{json.dumps(data, ensure_ascii=False, indent=2)}\n```\n")
        
        return "\n".join(markdown_parts)
    
    def _json_object_to_markdown(self, obj: Any, title: str = "JSON对象") -> str:
        """将单个JSON对象转换为markdown格式"""
        markdown_parts = [f"## {title}\n"]
        
        if isinstance(obj, dict):
            markdown_parts.append(self._dict_to_markdown(obj, 3))
        elif isinstance(obj, list):
            markdown_parts.append(self._list_to_markdown(obj, 3))
        else:
            markdown_parts.append(f"```json\n{json.dumps(obj, ensure_ascii=False, indent=2)}\n```\n")
        
        return "\n".join(markdown_parts)
    
    def _dict_to_markdown(self, data: Dict[str, Any], level: int) -> str:
        """将字典转换为markdown格式"""
        markdown_parts = []
        
        for key, value in data.items():
            # 创建键的标题
            header = "#" * min(level, 6)
            markdown_parts.append(f"{header} {key}\n")
            
            # 根据值的类型处理
            if isinstance(value, dict):
                if len(value) == 0:
                    markdown_parts.append("*空对象*\n")
                else:
                    markdown_parts.append(self._dict_to_markdown(value, level + 1))
            elif isinstance(value, list):
                if len(value) == 0:
                    markdown_parts.append("*空数组*\n")
                else:
                    markdown_parts.append(self._list_to_markdown(value, level + 1))
            else:
                # 基本类型：字符串、数字、布尔值等
                if isinstance(value, str) and len(value) > 100:
                    # 长字符串使用代码块
                    markdown_parts.append(f"```\n{value}\n```\n")
                else:
                    markdown_parts.append(f"**值:** `{json.dumps(value, ensure_ascii=False)}`\n")
        
        return "\n".join(markdown_parts)
    
    def _list_to_markdown(self, data: List[Any], level: int) -> str:
        """将列表转换为markdown格式"""
        markdown_parts = []
        
        # 如果列表很长，只显示前几项和统计信息
        if len(data) > 20:
            markdown_parts.append(f"**数组长度:** {len(data)} 项\n")
            markdown_parts.append("**前10项:**\n")
            display_items = data[:10]
        else:
            display_items = data
        
        for i, item in enumerate(display_items):
            if isinstance(item, dict):
                header = "#" * min(level, 6)
                markdown_parts.append(f"{header} 项目 {i + 1}\n")
                markdown_parts.append(self._dict_to_markdown(item, level + 1))
            elif isinstance(item, list):
                header = "#" * min(level, 6)
                markdown_parts.append(f"{header} 项目 {i + 1} (数组)\n")
                markdown_parts.append(self._list_to_markdown(item, level + 1))
            else:
                # 基本类型
                if isinstance(item, str) and len(item) > 100:
                    markdown_parts.append(f"**项目 {i + 1}:**\n```\n{item}\n```\n")
                else:
                    markdown_parts.append(f"**项目 {i + 1}:** `{json.dumps(item, ensure_ascii=False)}`\n")
        
        # 如果有更多项目，显示省略信息
        if len(data) > 20:
            markdown_parts.append(f"*... 还有 {len(data) - 10} 项 ...*\n")
        
        return "\n".join(markdown_parts)
    
    def get_supported_extensions(self) -> List[str]:
        return self.supported_extensions 