import os
import tempfile
import uuid
import subprocess
from typing import Tuple, List
from pathlib import Path
from .base_processor import BaseProcessor
from ..utils.ai_utils import AIUtils
import shutil

class ImageProcessor(BaseProcessor):
    """图片处理器"""
    
    def __init__(self):
        self.supported_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp']
        self.temp_dir = Path("temp/image_processing")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.ai_utils = AIUtils()
    
    def can_process(self, file_path: str) -> bool:
        """判断是否可以处理该文件类型"""
        file_ext = Path(file_path).suffix.lower()
        return file_ext in self.supported_extensions
    
    def extract_content(self, file_path: str) -> Tuple[str, List[str]]:
        """提取图片内容，转换为PNG格式并生成描述"""
        try:
            # 创建临时目录
            temp_id = str(uuid.uuid4())
            temp_extract_dir = self.temp_dir / temp_id
            temp_extract_dir.mkdir(exist_ok=True)
            
            try:
                # 1. 使用ffmpeg转换为PNG格式
                png_path = self._convert_to_png(file_path, temp_extract_dir)
                
                # 2. 使用AI工具生成图片描述
                image_description = self.ai_utils.get_image_description(png_path)
                
                # 3. 构建markdown内容
                original_filename = Path(file_path).name
                markdown_content = self._create_markdown_content(
                    original_filename, 
                    image_description, 
                    png_path
                )
                
                return markdown_content, [png_path]
                
            finally:
                # 清理临时目录
                if temp_extract_dir.exists():
                    shutil.rmtree(temp_extract_dir)
                    
        except Exception as e:
            raise Exception(f"图片处理器提取内容失败: {str(e)}")
    
    def _convert_to_png(self, input_path: str, output_dir: Path) -> str:
        """使用ffmpeg将图片转换为PNG格式"""
        try:
            input_file = Path(input_path)
            output_filename = f"{input_file.stem}.png"
            output_path = output_dir / output_filename
            
            # 检查ffmpeg是否可用
            if not self._check_ffmpeg_available():
                # 如果ffmpeg不可用，直接复制原文件（如果已经是PNG）或抛出异常
                if input_file.suffix.lower() == '.png':
                    shutil.copy2(input_path, output_path)
                    return str(output_path)
                else:
                    raise Exception("ffmpeg不可用，无法转换图片格式")
            
            # 使用ffmpeg转换
            cmd = [
                'ffmpeg',
                '-i', str(input_path),
                '-y',  # 覆盖输出文件
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                check=True
            )
            
            if not output_path.exists():
                raise Exception("ffmpeg转换失败，输出文件不存在")
            
            return str(output_path)
            
        except subprocess.CalledProcessError as e:
            raise Exception(f"ffmpeg转换失败: {e.stderr}")
        except Exception as e:
            raise Exception(f"图片格式转换失败: {str(e)}")
    
    def _check_ffmpeg_available(self) -> bool:
        """检查ffmpeg是否可用"""
        try:
            subprocess.run(
                ['ffmpeg', '-version'], 
                capture_output=True, 
                check=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _create_markdown_content(self, filename: str, description: str, image_path: str) -> str:
        """创建图片的markdown内容"""
        markdown_content = f"""# 图片文件: {filename}

## 图片描述

{description}

## 图片信息

- **原始文件名**: {filename}
- **处理后路径**: {image_path}
- **格式**: PNG

![{filename}]({image_path})

---

**注意**: 此内容由AI自动生成，描述了图片中的主要元素和信息。
"""
        
        return markdown_content
    
    def get_supported_extensions(self) -> List[str]:
        return self.supported_extensions