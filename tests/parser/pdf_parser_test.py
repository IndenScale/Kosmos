#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF解析器测试脚本 - 使用真实的PDF文件和PyMuPDF
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 设置环境变量
os.environ['OPENAI_BASE_URL'] = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
os.environ['OPENAI_API_KEY'] = 'dummy-key-for-test'
os.environ['OPENAI_VLM_MODEL'] = 'qwen-vl-max'

# 处理libmagic依赖问题
try:
    import magic
except ImportError:
    # 创建一个模拟的magic模块
    class MockMagic:
        def from_file(self, file_path, mime=True):
            if file_path.endswith('.pdf') or file_path.endswith('.PDF'):
                return 'application/pdf'
            return 'text/plain'
    
    import sys
    sys.modules['magic'] = MockMagic()
    import magic

# 简化测试，只导入必要的类
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path as Pathlib
import uuid
import time
import fitz  # PyMuPDF
import re

# 模拟必要的类和枚举
class FragmentType:
    TEXT = "text"
    SCREENSHOT = "screenshot"
    FIGURE = "figure"

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

class TextSplitter:
    """模拟文本分割器"""
    
    def __init__(self, chunk_size: int = 1350, chunk_overlap: int = 150):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def split_text(self, text: str) -> List[str]:
        """简单的文本分割实现"""
        if len(text) <= self.chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            
            # 如果不是最后一块，尝试在句号、换行符等处分割
            if end < len(text):
                # 寻找最近的句号或换行符
                for i in range(end, max(start + self.chunk_size - 200, start), -1):
                    if text[i] in '.。\n':
                        end = i + 1
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - self.chunk_overlap if end < len(text) else end
        
        return chunks

class MockModelClient:
    """模拟模型客户端"""
    
    def get_image_description(self, image_path: str) -> str:
        return f"这是图像 {Pathlib(image_path).name} 的描述"

class PdfParser:
    """PDF解析器 - 简化版本用于测试"""
    
    def __init__(self, db, kb_id):
        self.logger = type('Logger', (), {'info': print, 'error': print})()
        self.model_client = MockModelClient()

    def parse(self, file_path: str) -> List[ParsedFragment]:
        """解析PDF文件"""
        start_time = time.time()

        try:
            # 转换URL为本地路径
            self.logger.info(f"开始解析PDF文件: {file_path}")
            local_path = file_path  # 简化处理
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

            # 返回错误Fragment
            fragment = ParsedFragment(
                fragment_type=FragmentType.TEXT,
                raw_content=f"[PDF解析失败: {Pathlib(local_path).name}]",
                meta_info={"error": str(e)},
                fragment_index=0
            )

            return [fragment]

    def _create_page_screenshots(self, doc: fitz.Document, start_index: int) -> List[ParsedFragment]:
        """为每页创建截图Fragment"""
        fragments = []

        for page_num in range(len(doc)):
            try:
                # 创建截图Fragment（模拟）
                meta_info = {
                    "screenshot_path": f"page_{page_num + 1}.png",
                    "page_start": page_num + 1,
                    "page_end": page_num + 1,
                    "content_type": "screenshot"
                }
                
                fragment = ParsedFragment(
                    fragment_type=FragmentType.SCREENSHOT,
                    raw_content=f"Page {page_num + 1} Screenshot",
                    meta_info=meta_info,
                    fragment_index=start_index + page_num,
                    page_start=page_num + 1,
                    page_end=page_num + 1
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
                        # 创建图像占位符
                        placeholder = f"[FIGURE_{figure_counter}]"

                        figures.append({
                            'id': figure_counter,
                            'page_num': page_num + 1,
                            'image_path': f"figure_{figure_counter}.png",
                            'placeholder': placeholder,
                            'description': None  # 稍后填充
                        })

                        # 在文本中插入占位符
                        page_text += f"\n\n{placeholder}\n\n"
                        figure_counter += 1

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

        for i, figure in enumerate(figures):
            try:
                # 模拟图像处理
                description = f"这是图像 {figure['image_path']} 的描述"

                # 更新figure信息
                figure['description'] = description

                # 创建figure fragment
                meta_info = {
                    "image_path": figure['image_path'],
                    "page_start": figure['page_num'],
                    "page_end": figure['page_num'],
                    "content_type": "figure",
                    "description_length": len(description)
                }

                fragment = ParsedFragment(
                    fragment_type=FragmentType.FIGURE,
                    raw_content=figure['image_path'],
                    meta_info=meta_info,
                    fragment_index=start_index + i,
                    page_start=figure['page_num'],
                    page_end=figure['page_num']
                )
                fragments.append(fragment)

            except Exception as e:
                self.logger.error(
                    f"图像Fragment创建失败: 第{figure['page_num']}页, "
                    f"路径: {figure['image_path']}, 错误: {e}"
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

    def _extract_page_info(self, text_content: str) -> List[Tuple[int, int, int]]:
        """
        从文本内容中提取页面信息
        返回: [(start_pos, end_pos, page_num), ...] 页面范围列表
        """
        page_ranges = []
        last_pos = 0
        
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

    def _determine_chunk_pages(self, chunk: str, page_ranges: List[Tuple[int, int, int]], text_content: str) -> Tuple[Optional[int], Optional[int]]:
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

    def _split_text_with_intelligent_splitter(self, text_content: str, start_index: int, doc: fitz.Document) -> List[ParsedFragment]:
        """使用智能文本分割器分割文本"""
        try:
            # 使用智能文本分割器，目标长度1200-1500字符
            splitter = TextSplitter(chunk_size=1350, chunk_overlap=150)

            chunks = splitter.split_text(text_content)
            fragments = []

            # 解析文本内容中的页面信息
            page_ranges = self._extract_page_info(text_content)
            
            for i, chunk in enumerate(chunks):
                if chunk.strip():  # 跳过空白块
                    # 确定chunk的页面范围
                    page_start, page_end = self._determine_chunk_pages(chunk, page_ranges, text_content)
                    
                    meta_info = {
                        "content_type": "text",
                        "content_length": len(chunk),
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "splitter_type": "intelligent",
                        "page_start": page_start,
                        "page_end": page_end
                    }

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
            self.logger.error(f"智能文本分割失败: {e}")
            return []

def main():
    # 创建PDF解析器实例
    parser = PdfParser(None, "test_kb_id")
    
    # 测试PDF文件路径
    test_pdf_path = project_root / "tests" / "parser" / "测试PDF.pdf"
    
    if not test_pdf_path.exists():
        print(f"测试PDF文件不存在: {test_pdf_path}")
        return
    
    print(f"开始测试PDF解析器，测试文件: {test_pdf_path}")
    
    # 解析PDF文件
    try:
        fragments = parser.parse(str(test_pdf_path))
        
        # 输出结果到文件
        output_file = project_root / "tests" / "parser" / "pdf_parser_test_result.txt"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("PDF解析器测试结果\n")
            f.write("=" * 50 + "\n")
            f.write(f"测试文件: {test_pdf_path}\n")
            f.write(f"生成的Fragment数量: {len(fragments)}\n\n")
            
            for i, fragment in enumerate(fragments):
                f.write(f"Fragment {i+1}:\n")
                f.write(f"  类型: {fragment.fragment_type}\n")
                f.write(f"  索引: {fragment.fragment_index}\n")
                f.write(f"  页面起始: {fragment.page_start}\n")
                f.write(f"  页面结束: {fragment.page_end}\n")
                f.write(f"  元信息: {fragment.meta_info}\n")
                f.write(f"  内容预览: {fragment.raw_content[:200] if fragment.raw_content else 'None'}...\n")
                f.write("-" * 30 + "\n")
        
        print(f"测试完成，结果已保存到: {output_file}")
        
        # 打印一些统计信息
        page_start_values = [f.page_start for f in fragments if f.page_start is not None]
        page_end_values = [f.page_end for f in fragments if f.page_end is not None]
        
        print(f"Fragment类型统计:")
        type_counts = {}
        for fragment in fragments:
            type_counts[fragment.fragment_type] = type_counts.get(fragment.fragment_type, 0) + 1
        for type_name, count in type_counts.items():
            print(f"  {type_name}: {count}")
            
        print(f"页面范围统计:")
        if page_start_values:
            print(f"  page_start范围: {min(page_start_values)} - {max(page_start_values)}")
        else:
            print(f"  page_start范围: None")
            
        if page_end_values:
            print(f"  page_end范围: {min(page_end_values)} - {max(page_end_values)}")
        else:
            print(f"  page_end范围: None")
        
        # 验证页面范围逻辑
        print(f"\n详细页面范围信息:")
        text_fragments = [f for f in fragments if f.fragment_type == FragmentType.TEXT]
        for i, fragment in enumerate(text_fragments):
            print(f"  文本Fragment {i+1}: page_start={fragment.page_start}, page_end={fragment.page_end}")
            
    except Exception as e:
        print(f"解析PDF时出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()