"""Office文档解析器 - 完全基于PDF转换的Wrapper
文件: office_parsers.py
创建时间: 2024-12-19
修改时间: 2024-12-20
描述: 将所有Office文档（Word、Excel、PowerPoint）转换为PDF后移交给PDF解析器处理
"""

import os
import uuid
import subprocess
from typing import List
from pathlib import Path
import shutil

from app.parsers.base_parser import DocumentParser, ParsedFragment
from app.parsers.parser_utils import url_to_local_path
from app.schemas.fragment import FragmentType


class OfficeParserBase(DocumentParser):
    """Office文档解析器基类 - PDF转换Wrapper"""
    
    def _convert_and_parse_with_pdf(self, file_path: str, source_type: str) -> List[ParsedFragment]:
        """转换为PDF并使用PDF解析器处理"""
        # 创建临时目录
        temp_id = str(uuid.uuid4())
        project_root = Path(__file__).parent.parent.parent
        temp_dir = project_root / "data" / "temp" / f"{source_type}_conversion" / temp_id
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 转换为PDF
            pdf_path = self._convert_to_pdf(file_path, temp_dir, source_type)

            # 使用PDF解析器
            from app.parsers.pdf_parser import PdfParser
            pdf_parser = PdfParser(self.db, self.kb_id)

            # 解析PDF
            fragments = pdf_parser.parse(pdf_path)

            # 更新meta_info以反映原始文件类型
            for fragment in fragments:
                if fragment.meta_info:
                    fragment.meta_info['original_source_type'] = source_type
                    fragment.meta_info['original_source_file'] = Path(file_path).name
                    fragment.meta_info['conversion_method'] = f'{source_type}_to_pdf'
                    fragment.meta_info['processed_by'] = f'{source_type}_parser_wrapper'

            self.logger.info(f"{source_type.upper()}通过PDF解析成功: {file_path}, 生成{len(fragments)}个fragments")
            return fragments

        finally:
            # 清理临时目录
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    def _convert_to_pdf(self, source_path: str, output_dir: Path, source_type: str) -> str:
        """将Office文档转换为PDF（使用LibreOffice）"""
        local_path = url_to_local_path(source_path)
        source_file = Path(local_path)
        pdf_filename = f"{source_file.stem}.pdf"
        pdf_path = output_dir / pdf_filename

        try:
            self.logger.info(f"使用 LibreOffice 转换 {source_type.upper()} 到 PDF...")
            self._convert_with_libreoffice(local_path, str(pdf_path))

            # 检查期望的PDF文件是否存在
            if pdf_path.exists():
                self.logger.info(f"{source_type.upper()}转PDF成功 (LibreOffice): {local_path} -> {pdf_path}")
                return str(pdf_path)

            # 如果期望的PDF文件不存在，检查输出目录中是否有其他PDF文件
            if output_dir.exists():
                pdf_files = [f for f in output_dir.iterdir() if f.suffix.lower() == '.pdf']
                if pdf_files:
                    actual_pdf = pdf_files[0]
                    self.logger.info(f"找到转换后的PDF文件: {actual_pdf}")
                    return str(actual_pdf)

            raise Exception(f"PDF转换失败，未找到输出文件: {pdf_path}")

        except Exception as e:
            self.logger.error(f"{source_type.upper()}转PDF失败: {local_path}, 错误: {e}")
            raise

    def _convert_with_libreoffice(self, source_path: str, pdf_path: str):
        """使用LibreOffice转换Office文档为PDF"""
        try:
            # 检查LibreOffice是否可用
            if not self._check_libreoffice_available():
                raise Exception("LibreOffice未安装或不可用")

            # 获取输出目录
            output_dir = Path(pdf_path).parent

            # 构建LibreOffice命令
            cmd = [
                'libreoffice',
                '--headless',
                '--convert-to', 'pdf',
                '--outdir', str(output_dir),
                source_path
            ]

            self.logger.info(f"执行LibreOffice转换命令: {' '.join(cmd)}")

            # 执行转换
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )

            if result.returncode != 0:
                error_msg = f"LibreOffice转换失败，返回码: {result.returncode}"
                if result.stderr:
                    error_msg += f"\n错误输出: {result.stderr}"
                if result.stdout:
                    error_msg += f"\n标准输出: {result.stdout}"
                raise Exception(error_msg)

            self.logger.info(f"LibreOffice转换完成: {source_path}")

        except subprocess.TimeoutExpired:
            raise Exception("LibreOffice转换超时（5分钟）")
        except Exception as e:
            self.logger.error(f"LibreOffice转换异常: {e}")
            raise

    def _check_libreoffice_available(self) -> bool:
        """检查LibreOffice是否可用"""
        try:
            result = subprocess.run(
                ['libreoffice', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _create_error_fragment(self, file_path: str, error_message: str, source_type: str) -> List[ParsedFragment]:
        """创建错误Fragment"""
        meta_info = self._create_meta_info(
            error_type="parsing_error",
            error_message=error_message,
            source_file=Path(file_path).name,
            source_type=source_type,
            processed_by=f'{source_type}_parser_wrapper'
        )

        fragment = ParsedFragment(
            fragment_type=FragmentType.TEXT,
            raw_content=f"{source_type.upper()}文档解析失败: {Path(file_path).name}\n错误信息: {error_message}",
            meta_info=meta_info,
            fragment_index=0
        )

        return [fragment]


class DocxParser(OfficeParserBase):
    """Word文档解析器 - PDF转换Wrapper"""

    def can_parse(self, file_path: str, mime_type: str) -> bool:
        """判断是否可以解析该文件"""
        local_path = url_to_local_path(file_path)
        return (mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' or
                Path(local_path).suffix.lower() == '.docx')

    def parse(self, file_path: str) -> List[ParsedFragment]:
        """解析Word文档 - 完全通过PDF转换处理"""
        try:
            return self._convert_and_parse_with_pdf(file_path, 'docx')
        except Exception as e:
            self.logger.error(f"Word文档解析失败: {file_path}, 错误: {e}")
            return self._create_error_fragment(file_path, str(e), 'docx')


class XlsxParser(OfficeParserBase):
    """Excel文档解析器 - PDF转换Wrapper"""

    def can_parse(self, file_path: str, mime_type: str) -> bool:
        """判断是否可以解析该文件"""
        local_path = url_to_local_path(file_path)
        return (mime_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' or
                Path(local_path).suffix.lower() == '.xlsx')

    def parse(self, file_path: str) -> List[ParsedFragment]:
        """解析Excel文档 - 完全通过PDF转换处理"""
        try:
            return self._convert_and_parse_with_pdf(file_path, 'xlsx')
        except Exception as e:
            self.logger.error(f"Excel文档解析失败: {file_path}, 错误: {e}")
            return self._create_error_fragment(file_path, str(e), 'xlsx')


class PptxParser(OfficeParserBase):
    """PowerPoint文档解析器 - PDF转换Wrapper"""

    def can_parse(self, file_path: str, mime_type: str) -> bool:
        """判断是否可以解析该文件"""
        local_path = url_to_local_path(file_path)
        return (mime_type == 'application/vnd.openxmlformats-officedocument.presentationml.presentation' or
                Path(local_path).suffix.lower() == '.pptx')

    def parse(self, file_path: str) -> List[ParsedFragment]:
        """解析PowerPoint文档 - 完全通过PDF转换处理"""
        try:
            return self._convert_and_parse_with_pdf(file_path, 'pptx')
        except Exception as e:
            self.logger.error(f"PowerPoint文档解析失败: {file_path}, 错误: {e}")
            return self._create_error_fragment(file_path, str(e), 'pptx')