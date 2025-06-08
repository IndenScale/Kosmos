from abc import ABC, abstractmethod
from typing import Tuple, List, Dict, Any
from pathlib import Path

class BaseProcessor(ABC):
    """文档处理器基类"""
    
    @abstractmethod
    def can_process(self, file_path: str) -> bool:
        """判断是否可以处理该文件类型"""
        pass
    
    @abstractmethod
    def extract_content(self, file_path: str) -> Tuple[str, List[str]]:
        """提取文档内容
        
        Returns:
            Tuple[str, List[str]]: (markdown_text, image_paths)
        """
        pass
    
    def get_supported_extensions(self) -> List[str]:
        """获取支持的文件扩展名"""
        return []