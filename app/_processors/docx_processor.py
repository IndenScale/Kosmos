import os
import uuid
import subprocess
from typing import Tuple, List
from pathlib import Path
from app._processors.base_processor import BaseProcessor
from app._processors.pdf_processor import PDFProcessor
import shutil

class DocxProcessor(BaseProcessor):
    """DOCX文档处理器 - 转换为PDF进行统一处理"""

    def __init__(self):
        super().__init__()
        self.supported_extensions = ['.docx']
        self.temp_dir = Path("data/temp/figures")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.pdf_processor = PDFProcessor()

    def can_process(self, file_path: str) -> bool:
        """判断是否可以处理该文件类型"""
        file_ext = Path(file_path).suffix.lower()
        return file_ext in self.supported_extensions

    def _extract_content_impl(self, file_path: str) -> Tuple[str, List[str]]:
        """提取DOCX文档内容，转换为PDF后进行统一处理"""
        try:
            # 创建临时目录
            temp_id = str(uuid.uuid4())
            temp_extract_dir = self.temp_dir / temp_id
            temp_extract_dir.mkdir(exist_ok=True)

            try:
                # 1. 使用LibreOffice将DOCX转换为PDF
                pdf_path = self._convert_to_pdf(file_path, temp_extract_dir)

                # 2. 使用PDF处理器处理转换后的PDF
                markdown_text, screenshot_paths = self.pdf_processor._extract_content_impl(pdf_path)

                self.logger.info(f"DOCX转PDF处理完成: {file_path} -> {pdf_path}")

                return markdown_text, screenshot_paths

            finally:
                # 清理临时目录
                if temp_extract_dir.exists():
                    shutil.rmtree(temp_extract_dir)

        except Exception as e:
            raise Exception(f"DOCX处理器转换失败: {str(e)}")

    def _convert_to_pdf(self, docx_path: str, output_dir: Path) -> str:
        """将DOCX转换为PDF，自动选择可用的转换方法"""
        docx_file = Path(docx_path)
        pdf_filename = f"{docx_file.stem}.pdf"
        pdf_path = output_dir / pdf_filename

        # 按优先级尝试不同的转换方法
        conversion_methods = [
            ("LibreOffice", self._convert_with_libreoffice),
            ("docx2pdf", self._convert_with_docx2pdf),
            ("Microsoft Word COM", self._convert_with_word_com)
        ]

        for method_name, method_func in conversion_methods:
            try:
                self.logger.info(f"尝试使用 {method_name} 转换 DOCX 到 PDF...")
                method_func(docx_path, str(pdf_path))

                if pdf_path.exists():
                    self.logger.info(f"DOCX转PDF成功 ({method_name}): {docx_path} -> {pdf_path}")
                    return str(pdf_path)
                else:
                    self.logger.warning(f"{method_name} 转换完成但PDF文件不存在")

            except Exception as e:
                self.logger.warning(f"{method_name} 转换失败: {str(e)}")
                continue

        # 如果所有方法都失败，抛出异常
        raise Exception("所有DOCX转PDF方法都失败，请检查系统环境或安装相关依赖")

    def _convert_with_libreoffice(self, docx_path: str, pdf_path: str):
        """使用LibreOffice转换"""
        if not self._check_libreoffice_available():
            raise Exception("LibreOffice不可用")

        output_dir = Path(pdf_path).parent
        cmd = [
            'libreoffice',
            '--headless',
            '--convert-to', 'pdf',
            '--outdir', str(output_dir),
            str(docx_path)
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=60
        )

        if result.returncode != 0:
            raise Exception(f"LibreOffice转换失败: {result.stderr}")

    def _convert_with_docx2pdf(self, docx_path: str, pdf_path: str):
        """使用docx2pdf库转换（仅Windows）"""
        try:
            from docx2pdf import convert
            convert(docx_path, pdf_path)
        except ImportError:
            raise Exception("docx2pdf库未安装，请运行: pip install docx2pdf")
        except Exception as e:
            raise Exception(f"docx2pdf转换失败: {str(e)}")

    def _convert_with_word_com(self, docx_path: str, pdf_path: str):
        """使用Microsoft Word COM接口转换（仅Windows）"""
        import platform
        if platform.system() != "Windows":
            raise Exception("Word COM接口仅在Windows上可用")

        try:
            import comtypes.client

            # 启动Word应用程序
            word = comtypes.client.CreateObject('Word.Application')
            word.Visible = False

            try:
                # 打开DOCX文档
                doc = word.Documents.Open(os.path.abspath(docx_path))

                # 导出为PDF
                doc.ExportAsFixedFormat(
                    OutputFileName=os.path.abspath(pdf_path),
                    ExportFormat=17,  # PDF格式
                    OpenAfterExport=False,
                    OptimizeFor=0,
                    BitmapMissingFonts=True,
                    DocStructureTags=False,
                    CreateBookmarks=False
                )

                doc.Close()
            finally:
                word.Quit()

        except ImportError:
            raise Exception("comtypes库未安装或Microsoft Word未安装")
        except Exception as e:
            raise Exception(f"Word COM转换失败: {str(e)}")

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