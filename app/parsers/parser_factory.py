"""
解析器工厂
文件: parser_factory.py
创建时间: 2025-07-26
描述: 根据文件类型选择合适的解析器
"""

from typing import Optional, List
from pathlib import Path
import logging

from app.parsers.base_parser import BaseParser
from app.parsers.parser_utils import MimeTypeDetector, FileTypeClassifier, url_to_local_path
from app.parsers.text_parsers import PlainTextParser, MarkdownParser, CodeParser
from app.parsers.image_parsers import PngImageParser, GenericImageParser
from app.parsers.pdf_parser import PdfParser
from app.parsers.office_parsers import DocxParser, XlsxParser, PptxParser


class ParserFactory:
    """解析器工厂类"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.mime_detector = MimeTypeDetector()
        self.file_classifier = FileTypeClassifier()

        # 注册所有解析器
        self._parsers = [
            # PDF解析器
            PdfParser,

            # Office文档解析器
            DocxParser,
            XlsxParser,
            PptxParser,

            # 图像解析器
            PngImageParser,
            GenericImageParser,

            # 文本解析器（按优先级排序）
            MarkdownParser,
            CodeParser,
            PlainTextParser,  # 最后的回退选项
        ]

    def get_parser(self, file_path: str, db, kb_id: str) -> Optional[BaseParser]:
        """
        根据文件路径获取合适的解析器

        Args:
            file_path: 文件路径
            db: 数据库会话
            kb_id: 知识库ID

        Returns:
            合适的解析器实例，如果没有找到则返回None
        """
        try:
            # 检测MIME类型
            mime_type = self.mime_detector.detect_mime_type(file_path)

            # 分类文件类型
            file_type = self.file_classifier.classify_file(file_path)

            self.logger.info(f"文件解析: {file_path}, MIME类型: {mime_type}, 文件类型: {file_type}")

            # 查找合适的解析器
            for parser_class in self._parsers:
                try:
                    # 创建解析器实例
                    parser = parser_class(db, kb_id)

                    # 检查是否可以解析
                    if parser.can_parse(file_path, mime_type):
                        self.logger.info(f"选择解析器: {parser_class.__name__} for {file_path}")
                        return parser

                except Exception as e:
                    self.logger.error(f"解析器创建失败: {parser_class.__name__}, 错误: {e}")
                    continue

            # 没有找到合适的解析器
            self.logger.warning(f"未找到合适的解析器: {file_path}, MIME类型: {mime_type}")
            return None

        except Exception as e:
            self.logger.error(f"解析器选择失败: {file_path}, 错误: {e}")
            return None

    def get_supported_extensions(self) -> List[str]:
        """获取所有支持的文件扩展名"""
        extensions = set()

        # 文本文件
        extensions.update(['.txt', '.md', '.markdown', '.rst'])

        # 代码文件
        extensions.update([
            '.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.hpp',
            '.cs', '.php', '.rb', '.go', '.rs', '.swift', '.kt',
            '.html', '.css', '.scss', '.less', '.xml', '.json',
            '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf',
            '.sql', '.sh', '.bat', '.ps1', '.dockerfile'
        ])

        # 图像文件
        extensions.update(['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg'])

        # PDF文件
        extensions.add('.pdf')

        # Office文档
        extensions.update(['.docx', '.xlsx', '.pptx'])

        return sorted(list(extensions))

    def get_supported_mime_types(self) -> List[str]:
        """获取所有支持的MIME类型"""
        mime_types = [
            # 文本类型
            'text/plain',
            'text/markdown',
            'text/x-markdown',
            'text/html',
            'text/css',
            'text/javascript',
            'text/xml',
            'application/json',
            'application/xml',
            'application/yaml',
            'text/yaml',

            # 代码类型
            'text/x-python',
            'text/x-java-source',
            'text/x-c',
            'text/x-c++',
            'text/x-csharp',
            'text/x-php',
            'text/x-ruby',
            'text/x-go',
            'text/x-rust',
            'text/x-swift',
            'text/x-kotlin',
            'text/x-sql',
            'text/x-shellscript',
            'application/x-typescript',

            # 图像类型
            'image/png',
            'image/jpeg',
            'image/gif',
            'image/bmp',
            'image/webp',
            'image/svg+xml',

            # PDF类型
            'application/pdf',

            # Office文档类型
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        ]

        return sorted(mime_types)

    def is_supported_file(self, file_path: str) -> bool:
        """
        检查文件是否被支持

        Args:
            file_path: 文件路径

        Returns:
            是否支持该文件
        """
        try:
            # 转换URL为本地路径
            local_path = url_to_local_path(file_path)
            # 检查扩展名
            extension = Path(local_path).suffix.lower()
            if extension in self.get_supported_extensions():
                return True

            # 检查MIME类型
            mime_type = self.mime_detector.detect_mime_type(file_path)
            if mime_type in self.get_supported_mime_types():
                return True

            # 检查文件类型分类
            file_type = self.file_classifier.classify_file(file_path)
            return file_type != 'unsupported'

        except Exception as e:
            self.logger.error(f"文件支持检查失败: {file_path}, 错误: {e}")
            return False

    def get_parser_info(self, file_path: str) -> dict:
        """
        获取文件的解析器信息

        Args:
            file_path: 文件路径

        Returns:
            包含解析器信息的字典
        """
        try:
            # 转换URL为本地路径
            local_path = url_to_local_path(file_path)

            mime_type = self.mime_detector.detect_mime_type(file_path)
            file_type = self.file_classifier.classify_file(file_path)

            # 查找合适的解析器
            parser_class = None
            for parser_cls in self._parsers:
                try:
                    # 创建临时实例进行检查
                    temp_parser = parser_cls(None, None)
                    if temp_parser.can_parse(file_path, mime_type):
                        parser_class = parser_cls
                        break
                except:
                    continue

            return {
                'file_path': file_path,
                'local_path': local_path,
                'mime_type': mime_type,
                'file_type': file_type,
                'parser_class': parser_class.__name__ if parser_class else None,
                'supported': parser_class is not None,
                'extension': Path(local_path).suffix.lower()
            }

        except Exception as e:
            return {
                'file_path': file_path,
                'error': str(e),
                'supported': False
            }


# 全局工厂实例
parser_factory = ParserFactory()