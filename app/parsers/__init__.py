"""
解析器包初始化文件
文件: __init__.py
创建时间: 2025-07-26
描述: 导出解析器相关的类和工厂
"""

from app.parsers.base_parser import BaseParser, ParsedFragment
from app.parsers.parser_factory import ParserFactory, parser_factory
from app.parsers.parser_utils import (
    MimeTypeDetector,
    FileTypeClassifier,
    ModelClient,
    ImageProcessor
)

# 文本解析器
from app.parsers.text_parsers import (
    PlainTextParser,
    MarkdownParser,
    CodeParser
)

# 图像解析器
from app.parsers.image_parsers import (
    PngImageParser,
    GenericImageParser
)

# 文档解析器
from app.parsers.pdf_parser import PdfParser
from app.parsers.office_parsers import (
    DocxParser,
    XlsxParser,
    PptxParser
)

__all__ = [
    # 基础类
    'BaseParser',
    'ParsedFragment',

    # 工厂类
    'ParserFactory',
    'parser_factory',

    # 工具类
    'MimeTypeDetector',
    'FileTypeClassifier',
    'ModelClient',
    'ImageProcessor',

    # 文本解析器
    'PlainTextParser',
    'MarkdownParser',
    'CodeParser',

    # 图像解析器
    'PngImageParser',
    'GenericImageParser',

    # 文档解析器
    'PdfParser',
    'DocxParser',
    'XlsxParser',
    'PptxParser',
]