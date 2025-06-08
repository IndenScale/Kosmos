from typing import Optional
from .base_processor import BaseProcessor
from .generic_processor import GenericProcessor
from .docx_processor import DocxProcessor

class ProcessorFactory:
    """文档处理器工厂"""
    
    def __init__(self):
        self.processors = [
            DocxProcessor(),  # 优先使用专用处理器
            GenericProcessor(),  # 通用处理器作为后备
        ]
    
    def get_processor(self, file_path: str) -> Optional[BaseProcessor]:
        """根据文件路径获取合适的处理器"""
        for processor in self.processors:
            if processor.can_process(file_path):
                return processor
        
        # 如果没有找到匹配的处理器，返回通用处理器作为基线
        return GenericProcessor()
    
    def get_supported_extensions(self) -> list:
        """获取所有支持的文件扩展名"""
        extensions = set()
        for processor in self.processors:
            extensions.update(processor.get_supported_extensions())
        return list(extensions)