import os
import tempfile
import uuid
import subprocess
from typing import Tuple, List
from pathlib import Path
from .base_processor import BaseProcessor
from .pdf_processor import PDFProcessor
import shutil

class PptxProcessor(BaseProcessor):
    """PPTX文档处理器 - 转换为PDF进行统一处理"""
    
    def __init__(self):
        super().__init__()
        self.supported_extensions = ['.pptx', '.ppt']
        self.temp_dir = Path("temp/pptx_processing")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.pdf_processor = PDFProcessor()
    
    def can_process(self, file_path: str) -> bool:
        """判断是否可以处理该文件类型"""
        file_ext = Path(file_path).suffix.lower()
        return file_ext in self.supported_extensions
    
    def _extract_content_impl(self, file_path: str) -> Tuple[str, List[str]]:
        """提取PPTX文档内容，转换为PDF后进行统一处理"""
        try:
            # 创建临时目录
            temp_id = str(uuid.uuid4())
            temp_extract_dir = self.temp_dir / temp_id
            temp_extract_dir.mkdir(exist_ok=True)
            
            try:
                # 1. 使用LibreOffice将PPTX转换为PDF
                pdf_path = self._convert_to_pdf(file_path, temp_extract_dir)
                
                # 2. 使用PDF处理器处理转换后的PDF
                markdown_text, screenshot_paths = self.pdf_processor._extract_content_impl(pdf_path)
                
                self.logger.info(f"PPTX转PDF处理完成: {file_path} -> {pdf_path}")
                
                return markdown_text, screenshot_paths
                
            finally:
                # 清理临时目录
                if temp_extract_dir.exists():
                    shutil.rmtree(temp_extract_dir)
                    
        except Exception as e:
            raise Exception(f"PPTX处理器转换失败: {str(e)}")

    def _convert_to_pdf(self, pptx_path: str, output_dir: Path) -> str:
        """使用LibreOffice将PPTX转换为PDF"""
        try:
            # 检查LibreOffice是否可用
            if not self._check_libreoffice_available():
                raise Exception("LibreOffice不可用，无法转换PPTX到PDF")

            # 生成输出PDF路径
            pptx_file = Path(pptx_path)
            pdf_filename = f"{pptx_file.stem}.pdf"
            pdf_path = output_dir / pdf_filename

            # 使用LibreOffice转换
            cmd = [
                'libreoffice',
                '--headless',
                '--convert-to', 'pdf',
                '--outdir', str(output_dir),
                str(pptx_path)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=120  # PPTX转换可能需要更长时间
            )

            if not pdf_path.exists():
                raise Exception("LibreOffice转换失败，输出PDF文件不存在")

            self.logger.info(f"PPTX转PDF成功: {pptx_path} -> {pdf_path}")
            return str(pdf_path)

        except subprocess.CalledProcessError as e:
            raise Exception(f"LibreOffice转换失败: {e.stderr}")
        except subprocess.TimeoutExpired:
            raise Exception("LibreOffice转换超时")
        except Exception as e:
            raise Exception(f"PPTX转PDF失败: {str(e)}")

    def _check_libreoffice_available(self) -> bool:
        """检查LibreOffice是否可用"""
        try:
            subprocess.run(
                ['libreoffice', '--version'],
                capture_output=True,
                check=True,
                timeout=10
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def get_supported_extensions(self) -> List[str]:
        return self.supported_extensions