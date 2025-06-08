import os
import tempfile
import uuid
from typing import Tuple, List
from pathlib import Path
from .base_processor import BaseProcessor
import pypandoc
import zipfile
from PIL import Image
import shutil

class DocxProcessor(BaseProcessor):
    """DOCX文档处理器"""
    
    def __init__(self):
        self.supported_extensions = ['.docx']
        self.temp_dir = Path("temp/docx_processing")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    def can_process(self, file_path: str) -> bool:
        """判断是否可以处理该文件类型"""
        file_ext = Path(file_path).suffix.lower()
        return file_ext in self.supported_extensions
    
    def extract_content(self, file_path: str) -> Tuple[str, List[str]]:
        """提取DOCX文档内容和图片"""
        try:
            # 创建临时目录
            temp_id = str(uuid.uuid4())
            temp_extract_dir = self.temp_dir / temp_id
            temp_extract_dir.mkdir(exist_ok=True)
            
            try:
                # 1. 提取图片
                image_paths = self._extract_images(file_path, temp_extract_dir)
                
                # 2. 使用pypandoc转换为markdown
                markdown_text = pypandoc.convert_file(
                    file_path, 
                    'markdown',
                    extra_args=['--extract-media', str(temp_extract_dir)]
                )
                
                # 3. 处理图片引用
                markdown_text = self._process_image_references(markdown_text, image_paths)
                
                return markdown_text, image_paths
                
            finally:
                # 清理临时目录
                if temp_extract_dir.exists():
                    shutil.rmtree(temp_extract_dir)
                    
        except Exception as e:
            raise Exception(f"DOCX处理器提取内容失败: {str(e)}")
    
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
            print(f"提取图片失败: {str(e)}")
        
        return image_paths
    
    def _process_image_references(self, markdown_text: str, image_paths: List[str]) -> str:
        """处理markdown中的图片引用"""
        # 这里可以根据需要处理图片引用
        # 例如将相对路径转换为绝对路径，或者添加图片描述占位符
        
        for image_path in image_paths:
            image_name = Path(image_path).name
            # 在markdown中查找并替换图片引用
            markdown_text = markdown_text.replace(
                f"![](media/{image_name})",
                f"![{image_name}](media/{image_name})\n\n[图片描述占位符: {image_path}]\n"
            )
        
        return markdown_text
    
    def get_supported_extensions(self) -> List[str]:
        return self.supported_extensions