"""
基础解析器类
文件: base_parser.py
创建时间: 2025-07-26
描述: 定义解析器的基础接口和通用功能
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import logging
import uuid
import json
from datetime import datetime
from sqlalchemy.orm import Session

from app.schemas.fragment import FragmentType
from app.parsers.parser_utils import ModelClient

logger = logging.getLogger(__name__)


class ParsedFragment:
    """解析后的Fragment数据结构"""

    def __init__(
        self,
        fragment_type: FragmentType,
        raw_content: str,
        meta_info: Dict[str, Any],
        fragment_index: int = 0,
        page_start: Optional[int] = None,
        page_end: Optional[int] = None
    ):
        self.fragment_type = fragment_type
        self.raw_content = raw_content
        self.meta_info = meta_info
        self.fragment_index = fragment_index
        # 为了向后兼容和方便使用，保留 page_num
        # 如果 page_start 和 page_end 相同，则 page_num 为该值；否则为 None
        if page_start is not None and page_start == page_end:
            self.page_num = page_start
        elif page_start is not None and page_end is None: # 如果只提供了 start
             self.page_num = page_start
        else:
             self.page_num = None

        # 新增 page_start 和 page_end 属性
        self.page_start = page_start
        self.page_end = page_end if page_end is not None else page_start


class BaseParser(ABC):
    """解析器基类"""

    def __init__(self, db: Session, kb_id: str):
        self.db = db
        self.kb_id = kb_id
        self.model_client = ModelClient(db, kb_id)
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def can_parse(self, file_path: str, mime_type: str) -> bool:
        """判断是否可以解析该文件"""
        pass

    @abstractmethod
    def parse(self, file_path: str) -> List[ParsedFragment]:
        """解析文件，返回Fragment列表"""
        pass

    def get_parser_name(self) -> str:
        """获取解析器名称"""
        return self.__class__.__name__

    def _create_meta_info(self, **kwargs) -> Dict[str, Any]:
        """创建标准的meta_info"""
        meta_info = {
            "activated": True,
            "created_by": "parser",
            "parser_name": self.get_parser_name(),
            "created_at": datetime.utcnow().isoformat(),
            **kwargs
        }
        return meta_info


class TextParser(BaseParser):
    """文本类解析器基类"""

    def __init__(self, db: Session, kb_id: str):
        super().__init__(db, kb_id)

    def _split_text(self, text: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
        """简单的文本分割算法"""
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            # 如果不是最后一块，尝试在句号、换行符等处分割
            if end < len(text):
                # 寻找最近的句号或换行符
                for i in range(end, max(start + chunk_size - 200, start), -1):
                    if text[i] in '.。\n':
                        end = i + 1
                        break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - overlap if end < len(text) else end

        return chunks


class ImageParser(BaseParser):
    """图像类解析器基类"""

    def __init__(self, db: Session, kb_id: str):
        super().__init__(db, kb_id)

    def _process_image(self, image_path: str) -> Tuple[str, str]:
        """
        处理图像：转换为PNG并缩放
        返回: (处理后的图像路径, 图像描述)
        """
        from app.parsers.parser_utils import ImageProcessor

        # 转换为PNG
        png_path = ImageProcessor.convert_to_png(image_path)

        # 缩放图像
        resized_path = ImageProcessor.resize_image_if_needed(png_path, max_size=980)

        # 获取图像描述
        description = self.model_client.get_image_description(resized_path)

        return resized_path, description


class DocumentParser(BaseParser):
    """图文混合文档解析器基类"""

    def __init__(self, db: Session, kb_id: str):
        super().__init__(db, kb_id)

    def _create_screenshot_fragment(
        self,
        screenshot_path: str,
        page_num: int,
        fragment_index: int
    ) -> ParsedFragment:
        """创建截图Fragment"""
        meta_info = self._create_meta_info(
            screenshot_path=screenshot_path,
            page_start=page_num,
            page_end=page_num,
            content_type="screenshot"
        )

        return ParsedFragment(
            fragment_type=FragmentType.SCREENSHOT,
            raw_content=f"Page {page_num} Screenshot: {Path(screenshot_path).name}",
            meta_info=meta_info,
            fragment_index=fragment_index,
            page_start=page_num,
            page_end=page_num
        )

    def _create_figure_fragment(
        self,
        image_path: str,
        description: str,
        page_num: Optional[int],
        fragment_index: int
    ) -> ParsedFragment:
        """创建图表Fragment"""
        meta_info = self._create_meta_info(
            image_path=image_path,
            page_start=page_num,
            page_end=page_num,
            content_type="figure",
            description_length=len(description)
        )

        return ParsedFragment(
            fragment_type=FragmentType.FIGURE,
            raw_content=image_path,  # figure fragment的raw_content应该是图像路径，与PNG parser保持一致
            meta_info=meta_info,
            fragment_index=fragment_index,
            page_start=page_num,
            page_end=page_num
        )

    def _create_text_fragment(
        self,
        text: str,
        page_start: Optional[int],
        page_end: Optional[int],
        fragment_index: int,
        **extra_meta
    ) -> ParsedFragment:
        """创建文本Fragment"""
        meta_info = self._create_meta_info(
            content_length=len(text),
            page_start=page_start,
            page_end=page_end,
            content_type="text",
            **extra_meta
        )

        return ParsedFragment(
            fragment_type=FragmentType.TEXT,
            raw_content=text,
            meta_info=meta_info,
            fragment_index=fragment_index,
            page_start=page_start,
            page_end=page_end
        )