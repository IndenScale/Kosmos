import os
import tempfile
import uuid
from typing import Tuple, List
from pathlib import Path
from app.processors.base_processor import BaseProcessor
import pypandoc
import zipfile
from PIL import Image
import shutil

class DocxProcessor(BaseProcessor):
    """DOCX文档处理器"""

    def __init__(self):
        super().__init__()
        self.supported_extensions = ['.docx']
        self.temp_dir = Path("temp/docx_processing")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        # 引入AI工具用于图片描述
        from app.utils.ai_utils import AIUtils
        self.ai_utils = AIUtils()

    def can_process(self, file_path: str) -> bool:
        """判断是否可以处理该文件类型"""
        file_ext = Path(file_path).suffix.lower()
        return file_ext in self.supported_extensions

    def _extract_content_impl(self, file_path: str) -> Tuple[str, List[str]]:
        """提取DOCX文档内容，返回完整的markdown文本（不再返回图片路径）"""
        try:
            # 创建临时目录
            temp_id = str(uuid.uuid4())
            temp_extract_dir = self.temp_dir / temp_id
            temp_extract_dir.mkdir(exist_ok=True)

            try:
                # 1. 首先使用pypandoc转换为markdown（让Pandoc处理图片提取）
                markdown_text = pypandoc.convert_file(
                    file_path,
                    'markdown',
                    extra_args=['--extract-media', str(temp_extract_dir)]
                )

                # 2. 获取Pandoc提取的图片路径
                media_dir = temp_extract_dir / "media"
                image_paths = []
                if media_dir.exists():
                    for img_file in media_dir.glob("*"):
                        if img_file.is_file():
                            image_paths.append(str(img_file))

                # 3. 处理图片：生成描述并嵌入markdown
                markdown_text = self._process_images_with_descriptions(markdown_text, image_paths)

                # 4. 返回完整的markdown文本，不再返回图片路径
                return markdown_text, []

            finally:
                # 清理临时目录（在processor内部完成所有处理后清理）
                if temp_extract_dir.exists():
                    shutil.rmtree(temp_extract_dir)

        except Exception as e:
            raise Exception(f"DOCX处理器提取内容失败: {str(e)}")

    def _process_images_with_descriptions(self, markdown_text: str, image_paths: List[str]) -> str:
        """处理图片：生成描述并直接嵌入markdown文本"""
        for image_path in image_paths:
            try:
                # 生成图片描述
                description = self.ai_utils.get_image_description(image_path)

                # 获取图片文件名
                image_name = Path(image_path).name

                # 替换markdown中的图片引用为描述文本
                old_reference = f"![](media/{image_name})"
                new_content = f"\n\n**图片内容**: {description}\n\n"

                if old_reference in markdown_text:
                    markdown_text = markdown_text.replace(old_reference, new_content)
                else:
                    # 如果没有找到精确匹配，尝试模糊匹配
                    import re
                    pattern = f"!\[.*?\]\(.*?{re.escape(image_name)}.*?\)"
                    markdown_text = re.sub(pattern, new_content, markdown_text)

                self.logger.info(f"已处理图片描述: {image_name}")

            except Exception as e:
                self.logger.warning(f"处理图片描述失败 {image_path}: {str(e)}")
                # 失败时使用占位符
                image_name = Path(image_path).name
                old_reference = f"![](media/{image_name})"
                fallback_content = f"\n\n**图片内容**: [图片描述生成失败]\n\n"
                markdown_text = markdown_text.replace(old_reference, fallback_content)

        return markdown_text

    def _extract_images(self, docx_path: str, extract_dir: Path) -> List[str]:
        """从DOCX文件中提取图片"""
        image_paths = []

        try:
            with zipfile.ZipFile(docx_path, 'r') as docx_zip:
                # 查找图片文件
                for file_info in docx_zip.filelist:
                    if file_info.filename.startswith('word/media/'):
                        # 提取图片
                        image_data = docx_zip.read(file_info.filename)

                        # 生成图片文件名
                        image_name = Path(file_info.filename).name
                        image_path = extract_dir / image_name

                        # 保存图片
                        with open(image_path, 'wb') as img_file:
                            img_file.write(image_data)

                        image_paths.append(str(image_path))

        except Exception as e:
            self.logger.warning(f"提取图片失败: {str(e)}")

        return image_paths

    def get_supported_extensions(self) -> List[str]:
        return self.supported_extensions