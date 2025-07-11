import re
from typing import Tuple, List, Dict
from pathlib import Path
from .base_processor import BaseProcessor


class CodeProcessor(BaseProcessor):
    """代码文件处理器，支持多种编程语言的智能分割"""
    
    def __init__(self):
        super().__init__()
        # 支持的代码文件扩展名
        self.supported_extensions = [
            '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.c', '.cpp', '.cc', '.cxx',
            '.h', '.hpp', '.cs', '.php', '.rb', '.go', '.rs', '.swift', '.kt', '.scala',
            '.r', '.m', '.mm', '.pl', '.sh', '.bash', '.zsh', '.ps1', '.sql', '.html',
            '.css', '.scss', '.sass', '.less', '.xml', '.yaml', '.yml', '.json',
            '.toml', '.ini', '.cfg', '.conf', '.dockerfile', '.makefile', '.cmake'
        ]
        
    def can_process(self, file_path: str) -> bool:
        """判断是否可以处理该文件类型"""
        file_ext = Path(file_path).suffix.lower()
        return file_ext in self.supported_extensions
    
    def _extract_content_impl(self, file_path: str) -> Tuple[str, List[str]]:
        """提取代码文件内容"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 检测编程语言
            language = self._detect_language(file_path)
            
            # 转换为markdown格式
            markdown_content = self._convert_to_markdown(content, language, file_path)
            
            # 代码文件通常不包含图片
            image_paths = []
            
            return markdown_content, image_paths
            
        except UnicodeDecodeError:
            # 尝试其他编码
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    content = f.read()
                language = self._detect_language(file_path)
                markdown_content = self._convert_to_markdown(content, language, file_path)
                return markdown_content, []
            except Exception as e:
                raise Exception(f"代码文件读取失败: {str(e)}")
        except Exception as e:
            raise Exception(f"代码处理器提取内容失败: {str(e)}")
    
    def _detect_language(self, file_path: str) -> str:
        """根据文件扩展名检测编程语言"""
        ext = Path(file_path).suffix.lower()
        
        language_map = {
            '.py': 'python',
            '.js': 'javascript', '.jsx': 'javascript', '.ts': 'javascript', '.tsx': 'javascript',
            '.java': 'java',
            '.c': 'cpp', '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp', '.h': 'cpp', '.hpp': 'cpp',
            '.cs': 'csharp',
            '.php': 'php',
            '.rb': 'ruby',
            '.go': 'go',
            '.rs': 'rust',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.r': 'r',
            '.m': 'objc', '.mm': 'objc',
            '.pl': 'perl',
            '.sh': 'bash', '.bash': 'bash', '.zsh': 'bash',
            '.ps1': 'powershell',
            '.sql': 'sql',
            '.html': 'html', '.htm': 'html',
            '.css': 'css', '.scss': 'scss', '.sass': 'sass', '.less': 'less',
            '.xml': 'xml',
            '.yaml': 'yaml', '.yml': 'yaml',
            '.json': 'json',
            '.toml': 'toml',
            '.ini': 'ini', '.cfg': 'ini', '.conf': 'ini',
            '.dockerfile': 'dockerfile',
            '.makefile': 'makefile',
            '.cmake': 'cmake'
        }
        
        return language_map.get(ext, 'text')
    
    def _convert_to_markdown(self, content: str, language: str, file_path: str) -> str:
        """将代码内容转换为markdown格式"""
        file_name = Path(file_path).name
        
        # 创建markdown格式的代码块
        markdown = f"# 代码文件: {file_name}\n\n"
        markdown += f"**文件路径**: `{file_path}`\n\n"
        markdown += f"**编程语言**: {language}\n\n"
        
        # 添加文件统计信息
        lines = content.split('\n')
        markdown += f"**文件统计**: {len(lines)} 行, {len(content)} 字符\n\n"
        
        # 添加代码内容
        markdown += f"```{language}\n{content}\n```\n\n"
        
        return markdown
    
    def get_supported_extensions(self) -> List[str]:
        return self.supported_extensions