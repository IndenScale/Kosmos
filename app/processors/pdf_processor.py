import os
import tempfile
import uuid
from typing import Tuple, List
from pathlib import Path
from app.processors.base_processor import BaseProcessor
import subprocess
import shutil
import json

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

    def can_process(self, file_path: str) -> bool:
        """判断是否可以处理该文件类型"""
        file_ext = Path(file_path).suffix.lower()
        return file_ext in self.supported_extensions

    def _extract_content_impl(self, file_path: str) -> Tuple[str, List[str]]:
        """提取PDF文档内容，生成页面截图并返回markdown文本和截图路径"""
        try:
            # 1. 生成页面截图
            screenshot_paths = self._generate_page_screenshots(file_path)
            
            # 2. 提取文本内容
            markdown_text = self._extract_text_content(file_path)
            
            # 3. 提取嵌入图片并使用VLM理解
            embedded_images = self._extract_and_process_images(file_path)
            
            # 4. 将图片描述嵌入到markdown中
            markdown_text = self._embed_image_descriptions(markdown_text, embedded_images)
            
            self.logger.info(f"PDF处理完成: {file_path}, 生成{len(screenshot_paths)}个页面截图")
            
            return markdown_text, screenshot_paths

        except Exception as e:
            raise Exception(f"PDF处理器提取内容失败: {str(e)}")

    def _generate_page_screenshots(self, pdf_path: str) -> List[str]:
        """生成PDF页面截图"""
        screenshot_paths = []
        
        try:
            # 使用pdf2image库生成截图
            try:
                from pdf2image import convert_from_path
                
                # 转换PDF页面为图片
                images = convert_from_path(pdf_path, dpi=200)
                
                for i, image in enumerate(images):
                    # 生成截图文件名
                    screenshot_filename = f"pdf_page_{i + 1}_{uuid.uuid4()}.png"
                    screenshot_path = self.screenshots_dir / screenshot_filename
                    
                    # 保存截图
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

    def _generate_screenshots_with_pymupdf(self, pdf_path: str) -> List[str]:
        """使用PyMuPDF生成截图的备选方案"""
        screenshot_paths = []
        
        try:
            import fitz  # PyMuPDF
            
            pdf_doc = fitz.open(pdf_path)
            
            for page_num in range(len(pdf_doc)):
                page = pdf_doc.load_page(page_num)
                
                # 设置渲染参数
                zoom = 2.0
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)
                
                # 生成截图文件名
                screenshot_filename = f"pdf_page_{page_num + 1}_{uuid.uuid4()}.png"
                screenshot_path = self.screenshots_dir / screenshot_filename
                
                # 保存截图
                pix.save(str(screenshot_path))
                screenshot_paths.append(str(screenshot_path))
                
                self.logger.info(f"使用PyMuPDF生成页面截图: 第{page_num + 1}页 -> {screenshot_path}")
            
            pdf_doc.close()
            
        except ImportError:
            self.logger.error("PyMuPDF也不可用，无法生成PDF截图")
        except Exception as e:
            self.logger.error(f"PyMuPDF生成截图失败: {str(e)}")
        
        return screenshot_paths

    def _extract_text_content(self, pdf_path: str) -> str:
        """提取PDF文本内容"""
        try:
            # 尝试使用PyMuPDF提取文本
            try:
                import fitz
                
                pdf_doc = fitz.open(pdf_path)
                text_content = []
                
                for page_num in range(len(pdf_doc)):
                    page = pdf_doc.load_page(page_num)
                    text = page.get_text()
                    text_content.append(f"\n\n## 第{page_num + 1}页\n\n{text}")
                
                pdf_doc.close()
                return "\n".join(text_content)
                
            except ImportError:
                # 如果PyMuPDF不可用，使用pypandoc
                self.logger.warning("PyMuPDF不可用，尝试使用pypandoc提取文本")
                return self._extract_text_with_pandoc(pdf_path)
            
        except Exception as e:
            self.logger.error(f"PDF文本提取失败: {str(e)}")
            return f"[PDF文本提取失败: {str(e)}]"

    def _extract_text_with_pandoc(self, pdf_path: str) -> str:
        """使用pypandoc提取PDF文本"""
        try:
            import pypandoc
            
            markdown_text = pypandoc.convert_file(pdf_path, 'markdown')
            return markdown_text
            
        except Exception as e:
            self.logger.error(f"pypandoc提取PDF文本失败: {str(e)}")
            return f"[PDF文本提取失败: {str(e)}]"

    def _extract_and_process_images(self, pdf_path: str) -> List[str]:
        """提取PDF中的嵌入图片并使用VLM处理"""
        image_descriptions = []
        
        try:
            import fitz
            
            pdf_doc = fitz.open(pdf_path)
            
            for page_num in range(len(pdf_doc)):
                page = pdf_doc.load_page(page_num)
                image_list = page.get_images()
                
                for img_index, img in enumerate(image_list):
                    try:
                        xref = img[0]
                        pix = fitz.Pixmap(pdf_doc, xref)
                        
                        if pix.n - pix.alpha < 4:  # 确保是RGB图像
                            # 生成临时图片文件
                            img_filename = f"pdf_embedded_img_{page_num + 1}_{img_index}_{uuid.uuid4()}.png"
                            img_path = self.temp_dir / img_filename
                            
                            pix.save(str(img_path))
                            
                            # 使用VLM理解图片
                            try:
                                description = self.ai_utils.get_image_description(str(img_path))
                                image_descriptions.append(description)
                                self.logger.info(f"VLM处理PDF嵌入图片: 第{page_num + 1}页")
                            except Exception as e:
                                self.logger.warning(f"VLM处理图片失败: {str(e)}")
                                image_descriptions.append("[图片描述生成失败]")
                            
                            # 清理临时图片文件
                            if img_path.exists():
                                os.remove(img_path)
                        
                        pix = None
                        
                    except Exception as e:
                        self.logger.warning(f"处理PDF嵌入图片失败: {str(e)}")
            
            pdf_doc.close()
            
        except ImportError:
            self.logger.warning("PyMuPDF不可用，跳过PDF嵌入图片处理")
        except Exception as e:
            self.logger.error(f"提取PDF嵌入图片失败: {str(e)}")
        
        return image_descriptions

    def _embed_image_descriptions(self, markdown_text: str, image_descriptions: List[str]) -> str:
        """将图片描述嵌入到markdown文本中"""
        if not image_descriptions:
            return markdown_text
        
        # 在markdown文本末尾添加图片描述
        image_section = "\n\n## 图片内容\n\n"
        for i, description in enumerate(image_descriptions):
            image_section += f"**图片 {i + 1}**: {description}\n\n"
        
        return markdown_text + image_section

    def get_supported_extensions(self) -> List[str]:
        return self.supported_extensions 