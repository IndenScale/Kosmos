from typing import Tuple, List
from pathlib import Path
from .base_processor import BaseProcessor
from markitdown import MarkItDown

class GenericProcessor(BaseProcessor):
    """通用文档处理器，使用markitdown提供基线服务"""
    
    def __init__(self):
        self.md = MarkItDown(enable_plugins=False)
        self.supported_extensions = [
            '.txt', '.pdf', '.xlsx', '.xls', '.pptx', '.ppt',
            '.csv', '.json', '.xml', '.html', '.htm', '.md'  # 添加 .md 支持
        ]
    
    def can_process(self, file_path: str) -> bool:
        """判断是否可以处理该文件类型"""
        file_ext = Path(file_path).suffix.lower()
        return file_ext in self.supported_extensions
    
    def extract_content(self, file_path: str) -> Tuple[str, List[str]]:
        """提取文档内容"""
        try:
            result = self.md.convert(file_path)
            markdown_text = result.text_content
            
            # markitdown通常不会提取图片文件，所以返回空列表
            image_paths = []
            
            return markdown_text, image_paths
            
        except Exception as e:
            raise Exception(f"通用处理器提取内容失败: {str(e)}")
    
    def get_supported_extensions(self) -> List[str]:
        return self.supported_extensions