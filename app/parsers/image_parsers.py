"""
图像解析器
文件: image_parsers.py
创建时间: 2025-07-26
描述: 实现各种图像类型的解析器
"""

from typing import List
from pathlib import Path

from app.parsers.base_parser import ImageParser, ParsedFragment
from app.parsers.parser_utils import url_to_local_path
from app.schemas.fragment import FragmentType


class PngImageParser(ImageParser):
    """PNG图像解析器"""

    def can_parse(self, file_path: str, mime_type: str) -> bool:
        """判断是否可以解析该文件"""
        local_path = url_to_local_path(file_path)
        return mime_type == 'image/png' or Path(local_path).suffix.lower() == '.png'

    def parse(self, file_path: str) -> List[ParsedFragment]:
        """解析PNG图像文件"""
        try:
            # 处理图像（缩放和获取描述）
            processed_path, description = self._process_image(file_path)

            fragments = []

            # 1. 创建figure fragment（图像本身）
            figure_meta_info = self._create_meta_info(
                original_path=file_path,
                processed_path=processed_path,
                image_format="PNG",
                description_length=len(description) if description else 0,
                content_type="figure",
                page_start=1,
                page_end=1
            )

            figure_fragment = ParsedFragment(
                fragment_type=FragmentType.FIGURE,
                raw_content=processed_path,  # figure fragment包含图像路径
                meta_info=figure_meta_info,
                fragment_index=0,
                page_start=1,
                page_end=1
            )
            fragments.append(figure_fragment)

            # 2. 创建text fragment（图像描述文本）
            # 只有当描述生成成功时才创建text fragment
            if description and not description.startswith("[图像描述生成失败"):
                text_meta_info = self._create_meta_info(
                    original_path=file_path,
                    processed_path=processed_path,
                    image_format="PNG",
                    content_length=len(description),
                    content_type="text",
                    source_type="image_description",
                    page_start=1,
                    page_end=1
                )

                text_fragment = ParsedFragment(
                    fragment_type=FragmentType.TEXT,
                    raw_content=f"**图像描述：**\n{description}",
                    meta_info=text_meta_info,
                    fragment_index=1,
                    page_start=1,
                    page_end=1
                )
                fragments.append(text_fragment)

            return fragments

        except Exception as e:
            self.logger.error(f"PNG图像解析失败: {file_path}, 错误: {e}")

            # 返回错误Fragment（只创建figure fragment）
            local_path = url_to_local_path(file_path)
            meta_info = self._create_meta_info(
                original_path=file_path,
                error=str(e),
                image_format="PNG",
                content_type="figure",
                page_start=1,
                page_end=1
            )

            fragment = ParsedFragment(
                fragment_type=FragmentType.FIGURE,
                raw_content=f"[PNG图像解析失败: {Path(local_path).name}]",
                meta_info=meta_info,
                fragment_index=0,
                page_start=1,
                page_end=1
            )

            return [fragment]


class GenericImageParser(ImageParser):
    """通用图像解析器"""

    def can_parse(self, file_path: str, mime_type: str) -> bool:
        """判断是否可以解析该文件"""
        # 支持所有图像类型
        local_path = url_to_local_path(file_path)
        return (mime_type.startswith('image/') or
                Path(local_path).suffix.lower() in [
                    '.jpg', '.jpeg', '.png', '.gif', '.bmp',
                    '.webp', '.tiff', '.ico', '.svg'
                ])

    def parse(self, file_path: str) -> List[ParsedFragment]:
        """解析通用图像文件"""
        try:
            # 获取图像格式
            image_format = self._get_image_format(file_path)

            # 处理图像（转换为PNG、缩放和获取描述）
            processed_path, description = self._process_image(file_path)

            fragments = []

            # 1. 创建figure fragment（图像本身）
            figure_meta_info = self._create_meta_info(
                original_path=file_path,
                processed_path=processed_path,
                original_format=image_format,
                processed_format="PNG",
                description_length=len(description) if description else 0,
                content_type="figure",
                page_start=1,
                page_end=1
            )

            figure_fragment = ParsedFragment(
                fragment_type=FragmentType.FIGURE,
                raw_content=processed_path,  # figure fragment包含图像路径
                meta_info=figure_meta_info,
                fragment_index=0,
                page_start=1,
                page_end=1
            )
            fragments.append(figure_fragment)

            # 2. 创建text fragment（图像描述文本）
            # 只有当描述生成成功时才创建text fragment
            if description and not description.startswith("[图像描述生成失败"):
                text_meta_info = self._create_meta_info(
                    original_path=file_path,
                    processed_path=processed_path,
                    original_format=image_format,
                    processed_format="PNG",
                    content_length=len(description),
                    content_type="text",
                    source_type="image_description",
                    page_start=1,
                    page_end=1
                )

                text_fragment = ParsedFragment(
                    fragment_type=FragmentType.TEXT,
                    raw_content=f"**图像描述：**\n{description}",
                    meta_info=text_meta_info,
                    fragment_index=1,
                    page_start=1,
                    page_end=1
                )
                fragments.append(text_fragment)

            return fragments

        except Exception as e:
            self.logger.error(f"图像解析失败: {file_path}, 错误: {e}")

            # 返回错误Fragment（只创建figure fragment）
            local_path = url_to_local_path(file_path)
            meta_info = self._create_meta_info(
                original_path=file_path,
                error=str(e),
                original_format=self._get_image_format(file_path),
                content_type="figure",
                page_start=1,
                page_end=1
            )

            fragment = ParsedFragment(
                fragment_type=FragmentType.FIGURE,
                raw_content=f"[图像解析失败: {Path(local_path).name}]",
                meta_info=meta_info,
                fragment_index=0,
                page_start=1,
                page_end=1
            )

            return [fragment]

    def _get_image_format(self, file_path: str) -> str:
        """获取图像格式"""
        local_path = url_to_local_path(file_path)
        ext = Path(local_path).suffix.lower()

        format_map = {
            '.jpg': 'JPEG',
            '.jpeg': 'JPEG',
            '.png': 'PNG',
            '.gif': 'GIF',
            '.bmp': 'BMP',
            '.webp': 'WebP',
            '.tiff': 'TIFF',
            '.ico': 'ICO',
            '.svg': 'SVG'
        }

        return format_map.get(ext, 'Unknown')