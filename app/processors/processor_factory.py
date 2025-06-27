from typing import Optional
from .base_processor import BaseProcessor
from .docx_processor import DocxProcessor
from .pptx_processor import PptxProcessor
from .pdf_processor import PDFProcessor
from .image_processor import ImageProcessor
from .code_processor import CodeProcessor
from .generic_processor import GenericProcessor

class ProcessorFactory:
    """处理器工厂类"""
    
    def __init__(self):
        self.processors = [
            PDFProcessor(),  # PDF处理器，支持截图
            DocxProcessor(),
            PptxProcessor(),
            ImageProcessor(),
            CodeProcessor(),
            GenericProcessor()  # 通用处理器作为后备
        ]
    
    def get_processor(self, file_path: str) -> BaseProcessor:
        """根据文件类型获取合适的处理器"""
        for processor in self.processors:
            if processor.can_process(file_path):
                return processor
        
        # 如果没有找到合适的处理器，返回通用处理器
        return self.processors[-1]
    
    def get_supported_extensions(self) -> list:
        """获取所有支持的文件扩展名"""
        extensions = set()
        for processor in self.processors:
            extensions.update(processor.get_supported_extensions())
        return list(extensions)