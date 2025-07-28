"""
Parser工具类
文件: parser_utils.py
创建时间: 2025-07-26
描述: 提供文件类型检测、模型调用等解析相关的工具功能
"""

import os
import mimetypes
import magic
import openai
import base64
import json
import logging
import re
from typing import Optional, Tuple, Dict, Any, List
from pathlib import Path
from urllib.parse import urlparse
from PIL import Image
from sqlalchemy.orm import Session

from app.models.credential import KBModelConfig, ModelAccessCredential
from app.services.credential_service import credential_service

logger = logging.getLogger(__name__)


def url_to_local_path(url: str) -> str:
    """将file:// URL转换为本地文件路径"""
    if url.startswith('file://'):
        # 解析file:// URL
        parsed = urlparse(url)
        # 在Windows上，路径可能是 /C:/path/to/file 格式
        path = parsed.path
        if os.name == 'nt' and path.startswith('/') and len(path) > 1 and path[2] == ':':
            # Windows路径，去掉开头的斜杠
            path = path[1:]
        return path
    return url


class MimeTypeDetector:
    """MIME类型检测器"""

    def __init__(self):
        # 初始化python-magic
        try:
            self.magic = magic.Magic(mime=True)
        except Exception as e:
            logger.warning(f"Failed to initialize python-magic: {e}")
            self.magic = None

    def detect_mime_type(self, file_path: str) -> str:
        """检测文件的MIME类型"""
        try:
            # 转换URL为本地路径
            local_path = url_to_local_path(file_path)

            # 首先尝试使用python-magic（更准确）
            if self.magic:
                mime_type = self.magic.from_file(local_path)
                if mime_type:
                    return mime_type

            # 回退到mimetypes模块
            mime_type, _ = mimetypes.guess_type(local_path)
            if mime_type:
                return mime_type

            # 如果都失败，根据扩展名手动判断
            return self._guess_mime_by_extension(local_path)

        except Exception as e:
            logger.error(f"MIME类型检测失败: {file_path}, 错误: {e}")
            return "application/octet-stream"

    def _guess_mime_by_extension(self, file_path: str) -> str:
        """根据文件扩展名猜测MIME类型"""
        ext = Path(file_path).suffix.lower()

        # 文本类型
        text_types = {
            '.txt': 'text/plain',
            '.md': 'text/markdown',
            '.py': 'text/x-python',
            '.js': 'text/javascript',
            '.ts': 'text/typescript',
            '.html': 'text/html',
            '.css': 'text/css',
            '.json': 'application/json',
            '.xml': 'text/xml',
            '.csv': 'text/csv',
            '.sql': 'text/x-sql',
            '.sh': 'text/x-shellscript',
            '.bat': 'text/x-msdos-batch',
            '.yaml': 'text/yaml',
            '.yml': 'text/yaml',
        }

        # 图像类型
        image_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.webp': 'image/webp',
            '.svg': 'image/svg+xml',
            '.tiff': 'image/tiff',
            '.ico': 'image/x-icon',
        }

        # 文档类型
        document_types = {
            '.pdf': 'application/pdf',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xls': 'application/vnd.ms-excel',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.ppt': 'application/vnd.ms-powerpoint',
            '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            '.odt': 'application/vnd.oasis.opendocument.text',
            '.ods': 'application/vnd.oasis.opendocument.spreadsheet',
            '.odp': 'application/vnd.oasis.opendocument.presentation',
        }

        # 视频类型（HLS切片等）
        video_types = {
            '.ts': 'video/mp2t',  # HLS切片文件
            '.m3u8': 'application/vnd.apple.mpegurl',
            '.mp4': 'video/mp4',
            '.avi': 'video/x-msvideo',
            '.mov': 'video/quicktime',
            '.wmv': 'video/x-ms-wmv',
            '.flv': 'video/x-flv',
        }

        # 合并所有类型
        all_types = {**text_types, **image_types, **document_types, **video_types}

        return all_types.get(ext, 'application/octet-stream')


class FileTypeClassifier:
    """文件类型分类器"""

    def __init__(self):
        self.mime_detector = MimeTypeDetector()

    def classify_file(self, file_path: str) -> str:
        """
        分类文件类型

        Args:
            file_path: 文件路径

        Returns:
            文件类型: 'pdf', 'office', 'image', 'text', 'markdown', 'code', 'unsupported'
        """
        try:
            # 转换URL为本地路径
            local_path = url_to_local_path(file_path)

            # 获取MIME类型和文件扩展名
            mime_type = self.mime_detector.detect_mime_type(file_path)
            file_ext = Path(local_path).suffix.lower()

            # PDF文件
            if mime_type == 'application/pdf' or file_ext == '.pdf':
                return 'pdf'

            # 图像文件
            if mime_type.startswith('image/') or file_ext in [
                '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.ico', '.svg'
            ]:
                return 'image'

            # Office文档
            office_mimes = [
                'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/vnd.ms-powerpoint',
                'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                'application/vnd.ms-excel',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'application/vnd.oasis.opendocument.text',
                'application/vnd.oasis.opendocument.presentation',
                'application/vnd.oasis.opendocument.spreadsheet',
            ]
            if mime_type in office_mimes:
                return 'office'

            # Markdown文件
            if mime_type == 'text/markdown' or file_ext in ['.md', '.markdown']:
                return 'markdown'

            # 代码文件
            code_mimes = [
                'text/x-python',
                'text/javascript',
                'text/typescript',
                'text/x-c',
                'text/x-c++',
                'text/x-java',
                'text/x-csharp',
                'text/x-php',
                'text/x-ruby',
                'text/x-go',
                'text/x-rust',
                'text/x-sql',
                'text/x-shellscript',
                'text/x-msdos-batch',
            ]
            code_exts = [
                '.py', '.js', '.ts', '.jsx', '.tsx', '.vue', '.java', '.c', '.cpp', '.h', '.hpp',
                '.cs', '.php', '.rb', '.go', '.rs', '.sql', '.sh', '.bat', '.ps1', '.r', '.scala',
                '.kt', '.swift', '.dart', '.lua', '.perl', '.pl', '.asm', '.s', '.vb', '.f90',
                '.m', '.mm', '.groovy', '.clj', '.hs', '.elm', '.ex', '.exs', '.erl', '.nim',
            ]

            if mime_type in code_mimes or file_ext in code_exts:
                return 'code'

            # 纯文本文件
            if mime_type.startswith('text/') or file_ext in ['.txt', '.log', '.cfg', '.conf', '.ini']:
                return 'text'

            # 其他不支持的类型
            return 'unsupported'

        except Exception as e:
            logger.error(f"文件分类失败: {file_path}, 错误: {e}")
            return 'unsupported'


class ModelClient:
    """模型客户端，用于调用知识库配置的模型"""

    def __init__(self, db: Session, kb_id: str):
        self.db = db
        self.kb_id = kb_id
        self._model_config = None
        self._clients = {}
        # 导入并初始化凭证服务
        from app.services.credential_service import credential_service
        self._credential_service = credential_service

    def _get_model_config(self) -> Optional[KBModelConfig]:
        """获取知识库的模型配置"""
        if not self._model_config:
            self._model_config = self.db.query(KBModelConfig).filter(
                KBModelConfig.kb_id == self.kb_id
            ).first()
        return self._model_config

    def _get_client(self, credential_id: str) -> openai.OpenAI:
        """获取OpenAI客户端"""
        if credential_id not in self._clients:
            credential = self.db.query(ModelAccessCredential).filter(
                ModelAccessCredential.id == credential_id
            ).first()

            if not credential:
                raise ValueError(f"未找到凭证: {credential_id}")

            # 解密API Key（这里需要实现解密逻辑）
            api_key = self._decrypt_api_key(credential.api_key_encrypted)

            self._clients[credential_id] = openai.OpenAI(
                api_key=api_key,
                base_url=credential.base_url
            )

        return self._clients[credential_id]

    def _decrypt_api_key(self, encrypted_key: str) -> str:
        """解密API Key"""
        return self._credential_service._decrypt_api_key(encrypted_key)

    def get_image_description(self, image_path: str) -> str:
        """使用VLM模型获取图像描述"""
        try:
            config = self._get_model_config()
            if not config or not config.vlm_credential_id:
                raise ValueError("知识库未配置VLM模型")

            client = self._get_client(config.vlm_credential_id)

            # 转换URL为本地路径
            local_path = url_to_local_path(image_path)

            # 读取并编码图像
            with open(local_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')

            response = client.chat.completions.create(
                model=config.vlm_model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "请详细描述这张图片的内容，包括主要元素、文字信息、图表数据等。描述要准确、详细，便于理解图片传达的信息。"
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                temperature=0.1,
                **(config.vlm_config_params or {})
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"图像描述生成失败: {image_path}, 错误: {e}")
            return f"[图像描述生成失败: {Path(image_path).name}]"


class ImageProcessor:
    """图像处理工具"""

    @staticmethod
    def resize_image_if_needed(image_path: str, max_size: int = 980) -> str:
        """如果图像任意一边超过指定大小，则按比例缩放"""
        try:
            # 转换URL为本地路径
            local_path = url_to_local_path(image_path)

            with Image.open(local_path) as img:
                width, height = img.size

                # 检查是否需要缩放
                if width <= max_size and height <= max_size:
                    return local_path

                # 计算缩放比例
                scale = min(max_size / width, max_size / height)
                new_width = int(width * scale)
                new_height = int(height * scale)

                # 缩放图像
                resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

                # 生成新的文件路径
                path_obj = Path(local_path)
                new_path = path_obj.parent / f"{path_obj.stem}_resized{path_obj.suffix}"

                # 保存缩放后的图像
                resized_img.save(new_path, optimize=True, quality=85)

                logger.info(f"图像已缩放: {local_path} -> {new_path} ({width}x{height} -> {new_width}x{new_height})")
                return str(new_path)

        except Exception as e:
            logger.error(f"图像缩放失败: {image_path}, 错误: {e}")
            return url_to_local_path(image_path)

    @staticmethod
    def convert_to_png(image_path: str) -> str:
        """将图像转换为PNG格式"""
        try:
            # 转换URL为本地路径
            local_path = url_to_local_path(image_path)
            path_obj = Path(local_path)

            if path_obj.suffix.lower() == '.png':
                return local_path

            with Image.open(local_path) as img:
                # 如果是RGBA模式，直接保存
                # 如果是其他模式，转换为RGB
                if img.mode in ('RGBA', 'LA'):
                    pass
                elif img.mode == 'P' and 'transparency' in img.info:
                    img = img.convert('RGBA')
                else:
                    img = img.convert('RGB')

                # 生成PNG文件路径
                png_path = path_obj.parent / f"{path_obj.stem}.png"
                img.save(png_path, 'PNG', optimize=True)

                logger.info(f"图像已转换为PNG: {local_path} -> {png_path}")
                return str(png_path)

        except Exception as e:
            logger.error(f"图像转换失败: {image_path}, 错误: {e}")
            return url_to_local_path(image_path)


class PageRangeUtils:
    """页面范围处理工具类"""

    @staticmethod
    def extract_page_info(text_content: str) -> List[Tuple[int, int, int]]:
        """
        从文本内容中提取页面信息
        返回: [(start_pos, end_pos, page_num), ...] 页面范围列表
        """
        page_ranges = []

        # 查找所有页面标记
        for match in re.finditer(r"--- Page (\d+) ---", text_content):
            page_num = int(match.group(1))
            start_pos = match.start()

            # 如果不是第一页，更新前一页的结束位置
            if page_ranges:
                page_ranges[-1] = (page_ranges[-1][0], start_pos, page_ranges[-1][2])

            # 添加当前页面的开始位置
            page_ranges.append((start_pos, len(text_content), page_num))

        return page_ranges

    @staticmethod
    def determine_chunk_pages(chunk: str, page_ranges: List[Tuple[int, int, int]], text_content: str) -> Tuple[Optional[int], Optional[int]]:
        """
        确定文本块的页面范围
        返回: (page_start, page_end)
        """
        if not page_ranges:
            # 如果没有页面信息，默认返回第一页
            return (1, 1)

        # 找到chunk在text_content中的位置
        chunk_start = text_content.find(chunk)
        if chunk_start == -1:
            # 如果找不到chunk，默认返回第一页
            return (1, 1)

        chunk_end = chunk_start + len(chunk)

        # 确定起始页
        page_start = None
        for start_pos, end_pos, page_num in page_ranges:
            if start_pos <= chunk_start < end_pos:
                page_start = page_num
                break

        # 确定结束页
        page_end = None
        for start_pos, end_pos, page_num in page_ranges:
            if start_pos < chunk_end <= end_pos:
                page_end = page_num
                break

        # 如果没有找到结束页，使用最后一个页面
        if page_end is None and page_ranges:
            page_end = page_ranges[-1][2]

        # 如果没有找到起始页，使用第一页
        if page_start is None and page_ranges:
            page_start = page_ranges[0][2]

        return (page_start, page_end)