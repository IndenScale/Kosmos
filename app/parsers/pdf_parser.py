# 文件: pdf_parser.py
# 创建时间: 2025-07-19
# 描述: 实现PDF文件的解析，使用mineru进行文档解析

import os
import re
import uuid
import traceback
import time
import subprocess
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from sqlalchemy.orm import Session
from .base_parser import DocumentParser, ParsedFragment
from .parser_utils import url_to_local_path
from app.schemas.fragment import FragmentType
from app.config import get_logger
from app.utils.text_splitter import TextSplitter
import shutil


class PdfParser(DocumentParser):
    """PDF解析器 - 使用mineru进行文档解析"""

    def __init__(self, db, kb_id):
        super().__init__(db, kb_id)
        self.logger = get_logger(self.__class__.__name__)
        # 从环境变量获取mineru路径
        self.mineru_path = os.getenv('MINERU_PATH', '/home/sdf/AssessmentSystem_v2/Kosmos/.venv/bin/mineru')
        # 初始化AI模型客户端用于图像描述生成
        try:
            from app.parsers.parser_utils import ModelClient
            self.model_client = ModelClient(db, kb_id)
        except Exception as e:
            self.logger.warning(f"无法初始化AI客户端，图像描述功能将被禁用: {e}")
            self.model_client = None

    def can_parse(self, file_path: str, mime_type: str) -> bool:
        """判断是否可以解析该文件"""
        local_path = url_to_local_path(file_path)
        return mime_type == 'application/pdf' or Path(local_path).suffix.lower() == '.pdf'

    def parse(self, file_path: str) -> List[ParsedFragment]:
        """解析PDF文件"""
        start_time = time.time()

        try:
            # 转换URL为本地路径
            self.logger.info(f"开始解析PDF文件: {file_path}")
            local_path = url_to_local_path(file_path)

            # 使用mineru解析PDF
            markdown_content, images_info, page_info_map = self._parse_with_mineru(local_path)

            fragments = []
            fragment_index = 0

            # 1. 处理图像并获取描述
            if images_info:
                # 在这一步，images_info中的description已经被填充
                figure_fragments = self._create_figure_fragments_sync(images_info, fragment_index)
                fragments.extend(figure_fragments)
                fragment_index += len(figure_fragments)

            # 2. 生成页面截图fragments
            screenshot_fragments = self._generate_page_screenshots(local_path, fragment_index, page_info_map)
            fragments.extend(screenshot_fragments)
            fragment_index += len(screenshot_fragments)

            # 3. 增强markdown内容，将图像的描述和图注注入
            enhanced_markdown = self._enhance_markdown_with_descriptions(markdown_content, images_info)

            # 4. 分割markdown内容，传入页面信息
            text_fragments = self._split_markdown_content(enhanced_markdown, fragment_index, page_info_map)
            fragments.extend(text_fragments)

            # 4. 合并小于500字符的fragments
            fragments = self._merge_small_fragments(fragments)

            # 记录解析耗时
            parse_duration = (time.time() - start_time) * 1000  # 转换为毫秒
            self.logger.info(f"PDF解析完成，耗时: {parse_duration:.2f}ms，生成{len(fragments)}个fragments")

            return fragments

        except Exception as e:
            parse_duration = (time.time() - start_time) * 1000
            self.logger.error(f"PDF解析失败: {file_path}, 耗时: {parse_duration:.2f}ms, 错误: {e}")
            self.logger.error(f"详细错误信息: {traceback.format_exc()}")

            # 返回错误Fragment
            local_path = url_to_local_path(file_path)
            meta_info = self._create_meta_info(
                error=str(e),
                file_path=file_path,
                parse_duration_ms=parse_duration
            )

            fragment = ParsedFragment(
                fragment_type=FragmentType.TEXT,
                raw_content=f"[PDF解析失败: {Path(local_path).name}]",
                meta_info=meta_info,
                fragment_index=0
            )

            return [fragment]

    def _parse_with_mineru(self, pdf_path: str) -> tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
        """使用mineru解析PDF文件"""
        try:
            # 创建输出目录
            pdf_name = Path(pdf_path).stem
            project_root = Path(__file__).parent.parent.parent
            output_dir = project_root / "data" / "temp" / f"mineru_output_{uuid.uuid4().hex[:8]}"
            output_dir.mkdir(parents=True, exist_ok=True)

            # 构建mineru命令
            cmd = [
                self.mineru_path,
                "-p", pdf_path,
                "-o", str(output_dir),
                "--backend", "pipeline",
                "--method", "txt"
            ]

            self.logger.info(f"执行mineru命令: {' '.join(cmd)}")

            # 执行mineru命令
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=3600  # 1小时超时
            )

            if result.returncode != 0:
                try:
                    stderr_decoded = result.stderr.decode('utf-8')
                except UnicodeDecodeError:
                    stderr_decoded = f"[mineru stderr 包含无法解码的二进制数据，长度: {len(result.stderr)} bytes]"
                raise Exception(f"mineru执行失败: {stderr_decoded}")

            # 查找生成的markdown文件
            markdown_files = list(output_dir.rglob("*.md"))
            if not markdown_files:
                raise Exception("未找到mineru生成的markdown文件")

            markdown_file = markdown_files[0]
            self.logger.info(f"找到markdown文件: {markdown_file}")

            # 读取markdown内容
            with open(markdown_file, 'r', encoding='utf-8') as f:
                markdown_content = f.read()

            # 读取content_list.json文件获取页面信息
            content_list_file = markdown_file.parent / f"{pdf_name}_content_list.json"
            page_info_map = {}
            if content_list_file.exists():
                page_info_map = self._parse_content_list(content_list_file)

            # 查找图像文件夹
            images_dir = markdown_file.parent / "images"
            images_info = []

            if images_dir.exists():
                # 提取markdown中的图像信息，包含页面信息
                images_info = self._extract_images_from_markdown(markdown_content, images_dir, page_info_map)

            return markdown_content, images_info, page_info_map

        except Exception as e:
            self.logger.error(f"mineru解析失败: {e}")
            raise

    def _parse_content_list(self, content_list_file: Path) -> Dict[str, int]:
        """解析content_list.json文件，提取文本和图像的页面信息"""
        try:
            with open(content_list_file, 'r', encoding='utf-8') as f:
                content_list = json.load(f)

            page_info_map = {}

            for item in content_list:
                if 'page_idx' in item:
                    page_num = item['page_idx'] + 1  # 转换为1-based页码

                    # 对于文本内容，使用内容作为key
                    if item.get('type') == 'text' and 'text' in item:
                        text_content = item['text'].strip()
                        if text_content:
                            page_info_map[text_content] = page_num

                    # 对于图像，使用图像路径作为key
                    elif item.get('type') == 'image' and 'img_path' in item:
                        img_path = item['img_path']
                        page_info_map[img_path] = page_num

            return page_info_map

        except Exception as e:
            self.logger.error(f"解析content_list.json失败: {e}")
            return {}

    def _enhance_markdown_with_descriptions(self, markdown_content: str, images_info: List[Dict[str, Any]]) -> str:
        """将图像的图注和描述注入到Markdown内容中，替换原始的图像链接。"""
        enhanced_content = markdown_content

        for img_info in images_info:
            # 构建图像的Markdown链接的正则表达式
            # ![alt_text](relative_path)
            # 使用更健壮的正则表达式，避免alt_text中的特殊字符导致问题
            pattern = re.compile(r'!\[' + re.escape(img_info['alt_text']) + r'\]\(' + re.escape(img_info['relative_path']) + r'\)')

            # 构建替换文本，包含图注和描述
            # 如果description为空，则只保留图注
            replacement = f"\n**{img_info.get('alt_text', '图示')}**"
            if img_info.get('description'):
                replacement += f"\n*图像描述: {img_info['description']}*\n"

            # 在Markdown内容中进行替换
            enhanced_content = pattern.sub(replacement, enhanced_content)

        return enhanced_content

    def _split_markdown_content(self, markdown_content: str, start_index: int, page_info_map: Dict[str, int] = None) -> List[ParsedFragment]:
        """分割Markdown内容，考虑到标题体系可能混乱的情况"""
        try:
            # 使用智能文本分割器
            splitter = TextSplitter(
                chunk_size=1500,
                chunk_overlap=200
            )

            chunks = splitter.split_text(markdown_content)
            fragments = []

            for i, chunk in enumerate(chunks):
                if not chunk.strip():
                    continue

                # 从页面信息映射中确定页面范围
                page_start, page_end = self._determine_chunk_pages_from_map(chunk, page_info_map)

                # 创建fragment的元数据
                meta_info = self._create_meta_info(
                    content_length=len(chunk),
                    chunk_index=i,
                    total_chunks=len(chunks),
                    source_type='pdf_markdown',
                    processed_by='mineru_pdf_parser',
                    page_start=page_start,
                    page_end=page_end
                )

                fragment = ParsedFragment(
                    fragment_type=FragmentType.TEXT,
                    raw_content=chunk.strip(),
                    meta_info=meta_info,
                    fragment_index=start_index + i,
                    page_start=page_start,
                    page_end=page_end
                )
                fragments.append(fragment)

            return fragments

        except Exception as e:
            self.logger.error(f"Markdown分割失败: {e}")
            # 回退到简单分割
            return self._simple_markdown_split(markdown_content, start_index)

        return fragments

    def _determine_chunk_pages_from_map(self, chunk: str, page_info_map: Dict[str, int]) -> tuple[int, int]:
        """从页面信息映射中确定文本块的页面范围"""
        if not page_info_map:
            return 1, 1

        pages = []
        chunk_lines = chunk.split('\n')

        # 查找chunk中的文本在page_info_map中的页面信息
        for line in chunk_lines:
            line = line.strip()
            if line:
                for text_key, page_num in page_info_map.items():
                    if line in text_key or text_key in line:
                        pages.append(page_num)
                        break

        if pages:
            return min(pages), max(pages)
        else:
            # 如果没有找到匹配，返回默认页面
            return 1, 1

    def _simple_markdown_split(self, markdown_content: str, start_index: int) -> List[ParsedFragment]:
        """简单的Markdown分割方法（回退方案）"""
        # 按段落分割
        paragraphs = [p.strip() for p in markdown_content.split('\n\n') if p.strip()]
        fragments = []

        for i, paragraph in enumerate(paragraphs):
            if len(paragraph) < 10:  # 跳过太短的段落
                continue

            meta_info = self._create_meta_info(
                content_length=len(paragraph),
                paragraph_index=i,
                total_paragraphs=len(paragraphs),
                source_type='pdf_markdown_simple',
                processed_by='mineru_pdf_parser'
            )

            fragment = ParsedFragment(
                fragment_type=FragmentType.TEXT,
                raw_content=paragraph,
                meta_info=meta_info,
                fragment_index=start_index + i
            )
            fragments.append(fragment)

        return fragments

    def _merge_small_fragments(self, fragments: List[ParsedFragment]) -> List[ParsedFragment]:
        """合并小于500字符的文本fragments到相邻fragments"""
        if not fragments:
            return fragments

        merged_fragments = []
        i = 0

        while i < len(fragments):
            current_fragment = fragments[i]

            # 如果是图像fragment或者长度足够，直接添加
            if (current_fragment.fragment_type != FragmentType.TEXT or
                len(current_fragment.raw_content) >= 500):
                merged_fragments.append(current_fragment)
                i += 1
                continue

            # 当前fragment是小于500字符的文本fragment，需要合并
            # 尝试与下一个文本fragment合并
            merged = False
            if i + 1 < len(fragments):
                next_fragment = fragments[i + 1]
                if next_fragment.fragment_type == FragmentType.TEXT:
                    # 合并到下一个fragment
                    merged_content = current_fragment.raw_content + "\n\n" + next_fragment.raw_content

                    # 更新meta_info
                    merged_meta = next_fragment.meta_info.copy() if next_fragment.meta_info else {}
                    merged_meta['merged_from_small_fragment'] = True
                    merged_meta['original_fragment_count'] = merged_meta.get('original_fragment_count', 1) + 1
                    merged_meta['content_length'] = len(merged_content)

                    merged_fragment = ParsedFragment(
                        fragment_type=FragmentType.TEXT,
                        raw_content=merged_content,
                        meta_info=merged_meta,
                        fragment_index=current_fragment.fragment_index,
                        page_start=min(current_fragment.page_start, next_fragment.page_start),
                        page_end=max(current_fragment.page_end, next_fragment.page_end)
                    )

                    merged_fragments.append(merged_fragment)
                    i += 2  # 跳过下一个fragment，因为已经合并了
                    merged = True

            # 如果无法与下一个合并，尝试与前一个合并
            if not merged and merged_fragments:
                prev_fragment = merged_fragments[-1]
                if prev_fragment.fragment_type == FragmentType.TEXT:
                    # 合并到前一个fragment
                    merged_content = prev_fragment.raw_content + "\n\n" + current_fragment.raw_content

                    # 更新meta_info
                    merged_meta = prev_fragment.meta_info.copy() if prev_fragment.meta_info else {}
                    merged_meta['merged_from_small_fragment'] = True
                    merged_meta['original_fragment_count'] = merged_meta.get('original_fragment_count', 1) + 1
                    merged_meta['content_length'] = len(merged_content)

                    # 更新前一个fragment
                    merged_fragments[-1] = ParsedFragment(
                        fragment_type=FragmentType.TEXT,
                        raw_content=merged_content,
                        meta_info=merged_meta,
                        fragment_index=prev_fragment.fragment_index,
                        page_start=min(prev_fragment.page_start, current_fragment.page_start),
                        page_end=max(prev_fragment.page_end, current_fragment.page_end)
                    )
                    merged = True

            # 如果都无法合并，保留原fragment（虽然很小）
            if not merged:
                merged_fragments.append(current_fragment)

            i += 1

        self.logger.info(f"Fragment合并完成: {len(fragments)} -> {len(merged_fragments)}")
        return merged_fragments

    def _extract_images_from_markdown(self, markdown_content: str, images_dir: Path, page_info_map: Dict[str, int] = None) -> List[Dict[str, Any]]:
        """从markdown内容中提取图像信息"""
        images_info = []

        # 匹配markdown中的图像引用
        image_pattern = r'!\[([^\]]*)\]\(([^\)]+)\)'
        matches = re.finditer(image_pattern, markdown_content)

        for i, match in enumerate(matches):
            alt_text = match.group(1)
            image_path = match.group(2)

            # 构建完整的图像路径
            if image_path.startswith('images/'):
                full_image_path = images_dir.parent / image_path
            else:
                full_image_path = images_dir / image_path

            if full_image_path.exists():
                # 从页面信息映射中获取页面信息
                page_start, page_end = self._get_image_page_from_map(image_path, alt_text, page_info_map)

                images_info.append({
                    'id': i,
                    'alt_text': alt_text,
                    'image_path': str(full_image_path),
                    'relative_path': image_path,
                    'description': None,  # 稍后填充
                    'page_start': page_start,
                    'page_end': page_end
                })

        return images_info

    def _get_image_page_from_map(self, image_path: str, alt_text: str, page_info_map: Dict[str, int]) -> tuple[int, int]:
        """从页面信息映射中获取图像的页面信息"""
        if not page_info_map:
            return 1, 1

        # 首先尝试通过图像路径匹配
        for path_key, page_num in page_info_map.items():
            if image_path in path_key or path_key.endswith(image_path):
                return page_num, page_num

        # 如果通过路径找不到，尝试通过alt_text匹配
        if alt_text:
            for text_key, page_num in page_info_map.items():
                if alt_text in text_key or text_key in alt_text:
                    return page_num, page_num

        # 如果都找不到，返回默认页面
        return 1, 1

    def _create_figure_fragments_sync(self, images_info: List[Dict[str, Any]], start_index: int) -> List[ParsedFragment]:
        """同步创建图像fragments（回退方案）"""
        fragments = []

        for i, img_info in enumerate(images_info):
            try:
                # 同步处理图像
                from app.parsers.parser_utils import ImageProcessor

                # 转换为PNG
                png_path = ImageProcessor.convert_to_png(img_info['image_path'])

                # 缩放图像
                resized_path = ImageProcessor.resize_image_if_needed(png_path, max_size=980)

                # 获取图像描述
                if self.model_client:
                    description = self.model_client.get_image_description(resized_path)
                else:
                    description = f"[图像描述生成功能未启用: {img_info.get('alt_text', '')}]"

                # 更新图像信息
                img_info['description'] = description
                img_info['processed_path'] = resized_path

                # 创建fragment
                fragment = self._create_figure_fragment(
                    resized_path,
                    description,
                    img_info.get('alt_text', ''),
                    start_index + i,
                    img_info.get('page_start', 1),
                    img_info.get('page_end', 1)
                )
                fragments.append(fragment)

            except Exception as e:
                self.logger.error(f"同步图像处理失败: {img_info['image_path']}, 错误: {e}")
                # 创建错误fragment
                img_info['description'] = f"[图像描述生成失败: {img_info.get('alt_text', '')}]"
                fragment = self._create_figure_fragment(
                    img_info['image_path'],
                    img_info['description'],
                    img_info.get('alt_text', ''),
                    start_index + i,
                    img_info.get('page_start', 1),
                    img_info.get('page_end', 1)
                )
                fragments.append(fragment)

        return fragments

    # 以下方法已被新的mineru解析流程替代，保留用于兼容性
    def _extract_content_and_figures_legacy(self, doc) -> tuple[str, List[Dict[str, Any]]]:
        """旧版PDF内容提取方法（已弃用，保留用于兼容性）"""
        self.logger.warning("使用旧版PDF提取方法，建议使用mineru解析")
        return "", []

    # 旧版图像处理方法（已弃用）
    def _create_figure_fragments_legacy(self, figures: List[Dict[str, Any]], start_index: int) -> List[ParsedFragment]:
        """旧版图像处理方法（已弃用，保留用于兼容性）"""
        self.logger.warning("使用旧版图像处理方法，建议使用新的mineru流程")
        return []

    def _create_figure_fragment(self, image_path: str, description: str, alt_text: str, fragment_index: int, page_start: int = 1, page_end: int = 1) -> ParsedFragment:
        """创建单个图表片段 - raw_content为图像URL"""
        return ParsedFragment(
            fragment_index=fragment_index,
            fragment_type=FragmentType.FIGURE,
            raw_content=image_path,  # 修改：raw_content为图像URL
            meta_info={
                "parser_type": "PdfParser",
                "content_length": 0,  # 图像URL长度不重要
                "image_path": image_path,
                "alt_text": alt_text,
                "description": description,  # 将描述存储在meta_info中
                "source_type": "mineru_pdf",
                "page_start": page_start,
                "page_end": page_end
            },
            page_start=page_start,
            page_end=page_end
        )

    def _generate_page_screenshots(self, pdf_path: str, start_index: int, page_info_map: Dict[str, int] = None) -> List[ParsedFragment]:
        """生成PDF页面截图fragments"""
        fragments = []

        try:
            # 导入PDF处理库
            import fitz  # PyMuPDF

            # 打开PDF文件
            doc = fitz.open(pdf_path)

            # 创建截图保存目录
            project_root = Path(__file__).parent.parent.parent
            screenshots_dir = project_root / "data" / "temp" / "screenshots"
            screenshots_dir.mkdir(parents=True, exist_ok=True)

            # 为每一页生成截图
            for page_num in range(len(doc)):
                try:
                    page = doc[page_num]

                    # 生成截图
                    mat = fitz.Matrix(2.0, 2.0)  # 2倍缩放以提高清晰度
                    pix = page.get_pixmap(matrix=mat)

                    # 保存截图
                    screenshot_filename = f"page_{page_num + 1}_{uuid.uuid4().hex[:8]}.png"
                    screenshot_path = screenshots_dir / screenshot_filename
                    pix.save(str(screenshot_path))

                    # 创建截图fragment
                    fragment = self._create_screenshot_fragment(
                        str(screenshot_path),
                        page_num + 1,  # 页码从1开始
                        start_index + page_num
                    )
                    fragments.append(fragment)

                except Exception as e:
                    self.logger.error(f"生成第{page_num + 1}页截图失败: {e}")
                    continue

            doc.close()
            self.logger.info(f"成功生成{len(fragments)}个页面截图fragments")

        except ImportError:
            self.logger.warning("PyMuPDF未安装，跳过页面截图生成")
        except Exception as e:
            self.logger.error(f"生成页面截图失败: {e}")

        return fragments

    def _create_screenshot_fragment(self, screenshot_path: str, page_num: int, fragment_index: int) -> ParsedFragment:
        """创建页面截图片段"""
        return ParsedFragment(
            fragment_index=fragment_index,
            fragment_type=FragmentType.SCREENSHOT,  # 修改：使用正确的fragment_type
            raw_content=screenshot_path,  # 修改：raw_content为截图URL
            meta_info={
                "parser_type": "PdfParser",
                "page_start": page_num,
                "page_end": page_num,
                "content_length": 0,
                "screenshot_path": screenshot_path,  # 使用screenshot_path字段
                "screenshot_type": "page_screenshot"
            },
            page_start=page_num,
            page_end=page_num
        )

    def _embed_figure_descriptions(self, text_content: str, figures: List[Dict[str, Any]]) -> str:
        """将图像描述嵌入文本中的占位符位置"""
        enhanced_text = text_content

        for figure in figures:
            if figure['description']:
                # 替换占位符为图像描述
                description_text = f"\n**图像描述 (第{figure['page_num']}页):**\n{figure['description']}\n"
                enhanced_text = enhanced_text.replace(figure['placeholder'], description_text)

        return enhanced_text

    def _split_text_content(self, text_content: str, start_index: int) -> List[ParsedFragment]:
        """使用Markdown解析器分割文本内容"""
        try:
            # 确保临时目录存在 - 使用绝对路径
            project_root = Path(__file__).parent.parent.parent
            temp_dir = project_root / "data" / "temp" / "figures"
            temp_dir.mkdir(parents=True, exist_ok=True)

            # 创建临时Markdown文件
            temp_md_filename = f"pdf_temp_{uuid.uuid4().hex[:8]}.md"
            temp_md_path = temp_dir / temp_md_filename

            with open(temp_md_path, 'w', encoding='utf-8') as f:
                f.write(text_content)

            # 使用Markdown解析器
            md_parser = MarkdownParser(self.db, self.kb_id)
            md_fragments = md_parser.parse(str(temp_md_path))

            # 更新fragment索引
            for i, fragment in enumerate(md_fragments):
                fragment.fragment_index = start_index + i
                # 添加PDF相关的元信息
                fragment.meta_info.update({
                    'source_type': 'pdf',
                    'processed_by': 'pdf_parser'
                })

            # 清理临时文件
            os.unlink(temp_md_path)

            return md_fragments

        except Exception as e:
            self.logger.error(f"文本分割失败: {e}")

            # 回退到简单分割
            return self._simple_text_split(text_content, start_index)
    def _split_text_with_intelligent_splitter(self, text_content: str, start_index: int) -> List[ParsedFragment]:
        """使用智能文本分割器分割文本，并正确标记页面信息"""
        try:
            # 使用智能文本分割器，目标长度1200-1500字符
            splitter = TextSplitter(chunk_size=1350, chunk_overlap=150)

            chunks = splitter.split_text(text_content)
            fragments = []

            for i, chunk in enumerate(chunks):
                if chunk.strip():  # 跳过空白块
                    meta_info = self._create_meta_info(
                        content_type="text",
                        content_length=len(chunk),
                        chunk_index=i,
                        total_chunks=len(chunks),
                        splitter_type="intelligent",
                        source_type="mineru_pdf"
                    )

                    fragment = ParsedFragment(
                        fragment_type=FragmentType.TEXT,
                        raw_content=chunk,
                        meta_info=meta_info,
                        fragment_index=start_index + i
                    )
                    fragments.append(fragment)

            self.logger.info(f"智能文本分割完成，生成{len(fragments)}个文本fragments")
            return fragments

        except Exception as e:
            self.logger.error(f"智能文本分割失败，回退到简单分割: {e}")
            # 回退到原有的分割方法
            return self._split_text_content(text_content, start_index)

    def _simple_text_split(self, text_content: str, start_index: int) -> List[ParsedFragment]:
        """简单的文本分割（回退方案）"""
        if not text_content.strip():
            return []

        # 按段落分割
        paragraphs = [p.strip() for p in text_content.split('\n\n') if p.strip()]

        fragments = []
        # 解析文本内容中的页面信息
        page_ranges = PageRangeUtils.extract_page_info(text_content)

        for i, paragraph in enumerate(paragraphs):
            if len(paragraph) < 50:  # 跳过太短的段落
                continue

            # 确定段落的页面范围
            page_start, page_end = PageRangeUtils.determine_chunk_pages(paragraph, page_ranges, text_content)

            meta_info = self._create_meta_info(
                content_length=len(paragraph),
                paragraph_index=i,
                total_paragraphs=len(paragraphs),
                source_type='pdf',
                processed_by='pdf_parser',
                page_start=page_start,
                page_end=page_end
            )

            fragment = ParsedFragment(
                fragment_type=FragmentType.TEXT,
                raw_content=paragraph,
                meta_info=meta_info,
                fragment_index=start_index + i,
                page_start=page_start,
                page_end=page_end
            )
            fragments.append(fragment)

        return fragments