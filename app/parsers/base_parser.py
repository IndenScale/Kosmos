"""基础解析器模块
文件: base_parser.py
创建时间: 2024-12-19
描述: 定义解析器的基础抽象类和通用功能
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from dataclasses import dataclass
from pathlib import Path

from app.schemas.fragment import FragmentType
from app.config import get_logger


@dataclass
class ParsedFragment:
    """解析后的文档片段"""
    fragment_type: FragmentType
    raw_content: str
    meta_info: Dict[str, Any] = None
    fragment_index: int = 0
    page_start: int = 1
    page_end: int = 1
        
    def __post_init__(self):
        """初始化meta_info"""
        if self.meta_info is None:
            self.meta_info = {}


class BaseParser(ABC):
    """解析器基类 - 定义所有解析器必须实现的基本接口"""
    
    @abstractmethod
    def can_parse(self, file_path: str, mime_type: str) -> bool:
        """判断是否可以解析该文件"""
        pass
    
    @abstractmethod
    def parse(self, file_path: str) -> List[ParsedFragment]:
        """解析文件并返回片段列表"""
        pass


class AbstractParser(BaseParser):
    """抽象解析器基类 - 提供通用功能实现"""
    
    def __init__(self, db=None, kb_id=None):
        self.db = db
        self.kb_id = kb_id
        self.logger = get_logger(self.__class__.__name__)
    
    def _create_meta_info(self, **kwargs) -> Dict[str, Any]:
        """创建元信息字典"""
        meta_info = {
            'parser_type': self.__class__.__name__,
            'file_name': Path(kwargs.get('original_path', '')).name if kwargs.get('original_path') else '',
        }
        
        # 添加其他提供的元信息
        for key, value in kwargs.items():
            if value is not None:
                meta_info[key] = value
                
        return meta_info


class DocumentParser(AbstractParser):
    """文档解析器基类 - 用于处理文档类型文件（PDF、Office、文本等）"""
    pass


class ImageParser(AbstractParser):
    """图像解析器基类 - 用于处理图像文件"""
    pass


class TextParser(AbstractParser):
    """文本解析器基类 - 用于处理纯文本文件"""
    pass