import os
import tempfile
import uuid
from typing import Tuple, List, Dict, Any
from pathlib import Path
from app.processors.base_processor import BaseProcessor
import subprocess
import shutil
import json
import fitz  # PyMuPDF

class PDFProcessor(BaseProcessor):
    """PDF文档处理器，支持页面截图"""

    def __init__(self):
        super().__init__()
        self.supported_extensions = ['.pdf']
        self.temp_dir = Path("temp/pdf_processing")
        self.screenshots_dir = Path("data/screenshots")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        
        # 引入AI工具用于图片描述
        from app.utils.ai_utils import AIUtils
        self.ai_utils = AIUtils()
        
        # 加载配置
        from app.config import config
        self.config = config.pdf_processor

    def can_process(self, file_path: str) -> bool:
        """判断是否可以处理该文件类型"""
        file_ext = Path(file_path).suffix.lower()
        return file_ext in self.supported_extensions

    def needs_screenshot(self, file_path: str) -> bool:
        """PDF文件需要生成截图"""
        return True

    def _extract_content_impl(self, file_path: str) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        提取PDF文档内容（重构为逐页处理模式，输出结构化内容块）
        """
        try:
            # 1. 生成页面截图（用于溯源）
            screenshot_paths = self._generate_page_screenshots(file_path)
            
            # 2. 逐页处理并收集结构化内容块
            all_content_blocks = []
            pdf_doc = self._open_pdf(file_path)
            if not pdf_doc:
                raise Exception("无法打开PDF文件")

            page_count = len(pdf_doc)
            for page_num in range(page_count):
                page_blocks = self._process_page_to_blocks(pdf_doc, page_num)
                all_content_blocks.extend(page_blocks)
            
            pdf_doc.close()
            
            self.logger.info(f"PDF处理完成: {file_path}, 共处理 {page_count} 页, 生成截图 {len(screenshot_paths)} 张")
            
            # 返回结构化块列表和截图路径
            return all_content_blocks, screenshot_paths

        except Exception as e:
            self.logger.error(f"PDF处理器提取内容失败: {file_path}, 错误: {str(e)}")
            raise

    def _open_pdf(self, file_path: str):
        """安全地打开PDF文件"""
        try:
            return fitz.open(file_path)
        except ImportError:
            self.logger.error("PyMuPDF (fitz) 未安装，无法处理PDF文件。请运行: pip install PyMuPDF")
            return None
        except Exception as e:
            self.logger.error(f"打开PDF文件失败: {file_path}, 错误: {e}")
            return None

    def _process_page_to_blocks(self, pdf_doc, page_num: int) -> List[Dict[str, Any]]:
        """处理单个页面，输出结构化内容块列表"""
        page = pdf_doc.load_page(page_num)
        blocks = []
        
        # 1. 添加页面标题块
        blocks.append({'type': 'heading', 'level': 2, 'content': f"第{page_num + 1}页"})
        
        # 2. 提取并添加文本块
        page_text = page.get_text("text").strip()
        if page_text:
            # 按段落拆分文本
            paragraphs = page_text.split('\n')
            for para in paragraphs:
                if para.strip():
                    blocks.append({'type': 'text', 'content': para.strip()})
        
        # 3. 提取、处理并添加图片描述块
        image_descriptions = self._process_embedded_images_on_page(pdf_doc, page)
        if image_descriptions:
            blocks.append({'type': 'heading', 'level': 3, 'content': "页面图片内容"})
            for i, desc in enumerate(image_descriptions):
                # 每个图片描述都是一个独立的、不可分割的块
                blocks.append({'type': 'image_description', 'content': f"**图片 {i+1}**: {desc}"})
                
        return blocks

    def _process_embedded_images_on_page(self, pdf_doc, page) -> List[str]:
        """提取并处理单个页面上的所有嵌入图片"""
        image_descriptions = []
        image_list = page.get_images(full=True)
        
        for img_index, img_info in enumerate(image_list):
            try:
                xref = img_info[0]
                pix = fitz.Pixmap(pdf_doc, xref)
                
                # 只处理RGB/Grayscale图片，忽略透明度层等
                if pix.n < 5:
                    img_filename = f"page_{page.number + 1}_img_{img_index}_{uuid.uuid4()}.png"
                    img_path = self.temp_dir / img_filename
                    
                    pix.save(str(img_path))
                    
                    try:
                        description = self.ai_utils.get_image_description(str(img_path))
                        if description and not description.startswith("[图片描述生成失败"):
                            image_descriptions.append(description)
                            self.logger.info(f"VLM处理PDF嵌入图片: 第{page.number + 1}页, 图片{img_index + 1}")
                        else:
                            self.logger.warning(f"VLM描述生成失败: 第{page.number + 1}页, 图片{img_index + 1}")
                    finally:
                        # 确保临时文件被删除
                        if img_path.exists():
                            os.remove(img_path)
                
                pix = None  # 释放Pixmap对象
            except Exception as e:
                self.logger.warning(f"处理第{page.number + 1}页的嵌入图片{img_index + 1}时出错: {e}")
                
        return image_descriptions

    def _generate_page_screenshots(self, pdf_path: str) -> List[str]:
        """生成PDF页面截图，如果截图已存在则直接返回现有路径"""
        screenshot_paths = []
        
        try:
            # 获取文档基础名称（不包含扩展名）
            doc_name = Path(pdf_path).stem
            
            # 首先检查是否已存在截图
            existing_screenshots = self._check_existing_screenshots(doc_name)
            if existing_screenshots:
                self.logger.info(f"发现现有PDF截图: {doc_name}, 共{len(existing_screenshots)}张，跳过生成")
                return existing_screenshots
            
            # 使用pdf2image库生成截图
            try:
                from pdf2image import convert_from_path
                
                # 转换PDF页面为图片
                images = convert_from_path(pdf_path, dpi=200)
                
                for i, image in enumerate(images):
                    # 生成截图文件名：文档名_页码.png
                    screenshot_filename = f"{doc_name}_page_{i + 1}.png"
                    screenshot_path = self.screenshots_dir / screenshot_filename
                    
                    # 保存截图（已确认不存在冲突）
                    image.save(str(screenshot_path), 'PNG')
                    screenshot_paths.append(str(screenshot_path))
                    
                    self.logger.info(f"生成PDF页面截图: 第{i + 1}页 -> {screenshot_path}")
                
            except ImportError:
                # 如果pdf2image不可用，使用PyMuPDF作为备选
                self.logger.warning("pdf2image不可用，尝试使用PyMuPDF生成截图")
                screenshot_paths = self._generate_screenshots_with_pymupdf(pdf_path)
            
        except Exception as e:
            self.logger.error(f"生成PDF截图失败: {pdf_path}, 错误: {str(e)}")
            # 如果截图生成失败，返回空列表，不影响文本处理
            screenshot_paths = []
        
        return screenshot_paths

    def _check_existing_screenshots(self, doc_name: str) -> List[str]:
        """检查是否已存在该文档的截图文件"""
        existing_screenshots = []
        
        try:
            # 检查截图目录中是否已存在该文档的截图
            for screenshot_file in self.screenshots_dir.glob(f"{doc_name}_page_*.png"):
                existing_screenshots.append(str(screenshot_file))
            
            # 按页码排序
            existing_screenshots.sort(key=lambda x: int(Path(x).stem.split('_page_')[1]))
            
        except Exception as e:
            self.logger.warning(f"检查现有截图时出错: {e}")
            existing_screenshots = []
        
        return existing_screenshots

    def _generate_screenshots_with_pymupdf(self, pdf_path: str) -> List[str]:
        """使用PyMuPDF生成截图的备选方案"""
        screenshot_paths = []
        
        try:
            # 获取文档基础名称（不包含扩展名）
            doc_name = Path(pdf_path).stem
            
            # 检查是否已存在截图
            existing_screenshots = self._check_existing_screenshots(doc_name)
            if existing_screenshots:
                self.logger.info(f"发现现有PDF截图(PyMuPDF): {doc_name}, 共{len(existing_screenshots)}张，跳过生成")
                return existing_screenshots
            
            pdf_doc = fitz.open(pdf_path)
            
            for page_num in range(len(pdf_doc)):
                page = pdf_doc.load_page(page_num)
                
                # 设置渲染参数
                zoom = 2.0
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)
                
                # 生成截图文件名：文档名_页码.png
                screenshot_filename = f"{doc_name}_page_{page_num + 1}.png"
                screenshot_path = self.screenshots_dir / screenshot_filename
                
                # 保存截图（已确认不存在冲突）
                pix.save(str(screenshot_path))
                screenshot_paths.append(str(screenshot_path))
                
                self.logger.info(f"使用PyMuPDF生成页面截图: 第{page_num + 1}页 -> {screenshot_path}")
            
            pdf_doc.close()
            
        except ImportError:
            self.logger.error("PyMuPDF也不可用，无法生成PDF截图")
        except Exception as e:
            self.logger.error(f"PyMuPDF生成截图失败: {str(e)}")
        
        return screenshot_paths

    def get_supported_extensions(self) -> List[str]:
        return self.supported_extensions 