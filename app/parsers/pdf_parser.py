# 文件: pdf_parser.py
# 创建时间: 2024-12-19
# 描述: 实现PDF文件的解析，支持文本提取和图像处理

import fitz  # PyMuPDF
import os
import uuid
import traceback
import time
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from sqlalchemy.orm import Session
from .base_parser import DocumentParser, ParsedFragment
from .text_parsers import MarkdownParser
from .parser_utils import url_to_local_path, PageRangeUtils
from app.schemas.fragment import FragmentType
from app.config import get_logger
from app.utils.text_splitter import TextSplitter
import shutil


class PdfParser(DocumentParser):
    """PDF解析器"""

    def __init__(self, db, kb_id):
        super().__init__(db, kb_id)
        self.logger = get_logger(self.__class__.__name__)

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
            doc = fitz.open(local_path)
            self.logger.info(f"PDF文件打开成功，共{len(doc)}页")
            fragments = []
            fragment_index = 0

            # 1. 生成每页截图
            screenshot_fragments = self._create_page_screenshots(doc, fragment_index)
            fragments.extend(screenshot_fragments)
            fragment_index += len(screenshot_fragments)

            # 2. 提取文本和图像
            text_content, figures = self._extract_content_and_figures(doc)

            # 3. 为图像生成描述并创建figure fragments
            figure_fragments = self._create_figure_fragments(figures, fragment_index)
            fragments.extend(figure_fragments)
            fragment_index += len(figure_fragments)

            # 4. 将图像描述嵌入文本中的占位符位置
            enhanced_text = self._embed_figure_descriptions(text_content, figures)

            # 5. 使用智能文本分割器分割文本
            text_fragments = self._split_text_with_intelligent_splitter(enhanced_text, fragment_index, doc)
            fragments.extend(text_fragments)

            doc.close()

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

    def _create_page_screenshots(self, doc: fitz.Document, start_index: int) -> List[ParsedFragment]:
        """为每页创建截图Fragment"""
        fragments = []

        # 确保临时目录存在
        temp_dir = Path("data/temp/figures")
        temp_dir.mkdir(parents=True, exist_ok=True)

        for page_num in range(len(doc)):
            try:
                page = doc[page_num]

                # 生成截图
                mat = fitz.Matrix(2.0, 2.0)  # 2倍缩放以提高清晰度
                pix = page.get_pixmap(matrix=mat)

                # 保存截图到指定目录
                screenshot_filename = f"pdf_page_{page_num + 1}_{uuid.uuid4().hex[:8]}.png"
                screenshot_path = temp_dir / screenshot_filename
                pix.save(str(screenshot_path))

                # 创建截图Fragment
                fragment = self._create_screenshot_fragment(
                    str(screenshot_path),
                    page_num + 1,
                    start_index + page_num
                )
                fragments.append(fragment)

            except Exception as e:
                self.logger.error(f"页面截图生成失败: 第{page_num + 1}页, 错误: {e}")

        return fragments

    def _extract_content_and_figures(self, doc: fitz.Document) -> Tuple[str, List[Dict[str, Any]]]:
        """提取文本内容和图像"""
        self.logger.info(f"开始提取PDF内容和图像")
        text_content = ""
        figures = []
        figure_counter = 0

        # 确保临时目录存在
        temp_dir = Path("data/temp/figures")
        temp_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"临时目录创建成功: {temp_dir}")

        for page_num in range(len(doc)):
            try:
                self.logger.info(f"开始处理第{page_num + 1}页")
                page = doc[page_num]

                # 提取文本
                try:
                    # 尝试使用markdown格式提取
                    page_text = page.get_text("markdown")
                except Exception as text_error:
                    self.logger.error(f"Markdown文本提取失败: 第{page_num + 1}页, 错误: {str(text_error)}")
                    try:
                        # 回退到普通文本提取
                        page_text = page.get_text()
                        self.logger.info(f"使用普通文本提取成功: 第{page_num + 1}页")
                    except Exception as fallback_error:
                        self.logger.error(f"普通文本提取也失败: 第{page_num + 1}页, 错误: {str(fallback_error)}")
                        page_text = ""

                # 提取图像
                try:
                    image_list = page.get_images()
                except Exception as img_list_error:
                    self.logger.error(f"图像列表获取失败: 第{page_num + 1}页, 错误: {str(img_list_error)}")
                    image_list = []

                for img_index, img in enumerate(image_list):
                    try:
                        # 获取图像数据
                        xref = img[0]
                        pix = fitz.Pixmap(doc, xref)

                        if pix.n - pix.alpha < 4:  # 确保不是CMYK
                            # 保存图像到指定目录
                            image_filename = f"pdf_figure_{figure_counter}_{uuid.uuid4().hex[:8]}.png"
                            image_path = temp_dir / image_filename
                            pix.save(str(image_path))

                            # 创建图像占位符
                            placeholder = f"[FIGURE_{figure_counter}]"

                            figures.append({
                                'id': figure_counter,
                                'page_num': page_num + 1,
                                'image_path': str(image_path),
                                'placeholder': placeholder,
                                'description': None  # 稍后填充
                            })

                            # 在文本中插入占位符
                            page_text += f"\n\n{placeholder}\n\n"
                            figure_counter += 1

                        pix = None

                    except Exception as e:
                        self.logger.error(f"图像提取失败: 第{page_num + 1}页, 图像{img_index}, 错误: {str(e)}")

                # 添加页面文本
                if page_text.strip():
                    text_content += f"\n\n--- Page {page_num + 1} ---\n\n{page_text}"

            except Exception as e:
                import traceback
                self.logger.error(f"页面内容提取失败: 第{page_num + 1}页, 错误: {str(e)}")
                self.logger.error(f"详细错误信息: {traceback.format_exc()}")

        return text_content, figures

    def _create_figure_fragments(self, figures: List[Dict[str, Any]], start_index: int) -> List[ParsedFragment]:
        """为图像创建figure fragments"""
        fragments = []

        if not figures:
            self.logger.info("PDF中没有检测到需要处理的图像")
            return fragments

        total_images = len(figures)
        self.logger.info(f"开始图像处理阶段: 共检测到 {total_images} 个图像需要处理")

        start_time = time.time()
        processed_count = 0
        failed_count = 0

        for i, figure in enumerate(figures):
            batch_index = i + 1

            # 进度日志：每10张图片记录一次
            if batch_index % 10 == 0 or batch_index == total_images:
                elapsed = time.time() - start_time
                avg_time = elapsed / batch_index
                self.logger.info(
                    f"图像处理进度: {batch_index}/{total_images} "
                    f"({batch_index/total_images*100:.1f}%) "
                    f"平均耗时: {avg_time:.2f}s/张"
                )

            try:
                image_start = time.time()

                # 处理图像并获取描述
                processed_path, description = self._process_image(figure['image_path'])

                # 计算单张耗时
                single_time = time.time() - image_start
                self.logger.debug(
                    f"图像处理完成: 第{figure['page_num']}页, "
                    f"耗时: {single_time:.2f}s, "
                    f"描述长度: {len(description)}字符"
                )

                # 更新figure信息
                figure['description'] = description
                figure['processed_path'] = processed_path

                # 创建figure fragment
                fragment = self._create_figure_fragment(
                    processed_path,
                    description,
                    figure['page_num'],
                    start_index + i
                )
                fragments.append(fragment)
                processed_count += 1

            except Exception as e:
                failed_count += 1
                self.logger.error(
                    f"图像Fragment创建失败: 第{figure['page_num']}页, "
                    f"路径: {figure['image_path']}, 错误: {e}"
                )

                # 创建错误Fragment
                figure['description'] = f"[图像描述生成失败: 第{figure['page_num']}页]"

                fragment = self._create_figure_fragment(
                    figure['image_path'],
                    figure['description'],
                    figure['page_num'],
                    start_index + i
                )
                fragments.append(fragment)

        # 阶段完成统计
        total_time = time.time() - start_time
        avg_time_per_image = total_time / total_images if total_images > 0 else 0

        self.logger.info(
            f"图像处理阶段完成: "
            f"总计 {total_images} 张, "
            f"成功 {processed_count} 张, "
            f"失败 {failed_count} 张, "
            f"总耗时: {total_time:.2f}s, "
            f"平均耗时: {avg_time_per_image:.2f}s/张"
        )

        return fragments

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
            # 确保临时目录存在
            temp_dir = Path("data/temp/figures")
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

    def _split_text_with_intelligent_splitter(self, text_content: str, start_index: int, doc: fitz.Document) -> List[ParsedFragment]:
        """使用智能文本分割器分割文本，并正确标记页面信息"""
        try:
            # 使用智能文本分割器，目标长度1200-1500字符
            splitter = TextSplitter(chunk_size=1350, chunk_overlap=150)

            chunks = splitter.split_text(text_content)
            fragments = []

            # 解析文本内容中的页面信息
            page_ranges = PageRangeUtils.extract_page_info(text_content)

            for i, chunk in enumerate(chunks):
                if chunk.strip():  # 跳过空白块
                    # 确定chunk的页面范围
                    page_start, page_end = PageRangeUtils.determine_chunk_pages(chunk, page_ranges, text_content)

                    meta_info = self._create_meta_info(
                        content_type="text",
                        content_length=len(chunk),
                        chunk_index=i,
                        total_chunks=len(chunks),
                        splitter_type="intelligent",
                        page_start=page_start,
                        page_end=page_end
                    )

                    fragment = ParsedFragment(
                        fragment_type=FragmentType.TEXT,
                        raw_content=chunk,
                        meta_info=meta_info,
                        fragment_index=start_index + i,
                        page_start=page_start,
                        page_end=page_end
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