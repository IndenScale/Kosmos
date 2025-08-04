"""解析器模块

提供各种文档解析器的统一接口
"""

from .base_parser import ParsedFragment
from .parser_factory import parser_factory

__all__ = ['ParsedFragment', 'parser_factory']