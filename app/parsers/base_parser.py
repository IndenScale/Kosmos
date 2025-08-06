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
    
    def __init__(self, db=None, kb_id=None):
        super().__init__(db, kb_id)
        # 初始化AI模型客户端用于图像描述生成
        try:
            from app.parsers.parser_utils import ModelClient
            self.model_client = ModelClient(db, kb_id) if db and kb_id else None
        except Exception as e:
            self.logger.warning(f"无法初始化AI客户端，图像描述功能将被禁用: {e}")
            self.model_client = None
    
    def _process_image(self, file_path: str) -> tuple[str, str]:
        """处理图像：转换格式、缩放并生成描述
        
        Args:
            file_path: 图像文件路径
            
        Returns:
            tuple: (处理后的图像路径, 图像描述)
        """
        try:
            from app.parsers.parser_utils import ImageProcessor
            
            # 转换为PNG格式
            png_path = ImageProcessor.convert_to_png(file_path)
            
            # 缩放图像到合适大小
            resized_path = ImageProcessor.resize_image_if_needed(png_path, max_size=980)
            
            # 获取图像描述
            if self.model_client:
                description = self.model_client.get_image_description(resized_path)
            else:
                description = f"[图像描述生成功能未启用: {Path(file_path).name}]"
            
            return resized_path, description
            
        except Exception as e:
            self.logger.error(f"图像处理失败: {file_path}, 错误: {e}")
            # 返回原始路径和错误描述
            from app.parsers.parser_utils import url_to_local_path
            local_path = url_to_local_path(file_path)
            return local_path, f"[图像处理失败: {Path(local_path).name}]"


class TextParser(AbstractParser):
    """文本解析器基类 - 用于处理纯文本文件"""
    pass