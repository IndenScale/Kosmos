import os
from typing import Tuple, List, Dict, Any
from pathlib import Path
import re
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
        
        # 不同语言的代码块分割模式
        self.language_patterns = {
            'python': {
                'function': r'^(def\s+\w+.*?:)$',
                'class': r'^(class\s+\w+.*?:)$',
                'import': r'^(import\s+.*|from\s+.*import\s+.*)$',
                'comment_block': r'^("""[\s\S]*?"""|\'\'\'\'[\s\S]*?\'\'\'\')$'
            },
            'javascript': {
                'function': r'^(function\s+\w+.*?\{|const\s+\w+\s*=.*?=>|\w+\s*:\s*function.*?\{)$',
                'class': r'^(class\s+\w+.*?\{)$',
                'import': r'^(import\s+.*|export\s+.*|require\s*\(.*\))$',
                'comment_block': r'^(/\*[\s\S]*?\*/)$'
            },
            'java': {
                'function': r'^(public|private|protected)?\s*(static)?\s*\w+\s+\w+\s*\(.*?\)\s*\{$',
                'class': r'^(public|private|protected)?\s*(abstract)?\s*(class|interface)\s+\w+.*?\{$',
                'import': r'^(import\s+.*|package\s+.*)$',
                'comment_block': r'^(/\*[\s\S]*?\*/)$'
            },
            'cpp': {
                'function': r'^(\w+\s+)*\w+\s*\(.*?\)\s*(const)?\s*\{$',
                'class': r'^(class|struct)\s+\w+.*?\{$',
                'include': r'^(#include\s+.*|#define\s+.*)$',
                'namespace': r'^(namespace\s+\w+.*?\{)$'
            },
            'go': {
                'function': r'^func\s+(\w+\s*)?\w+\s*\(.*?\).*?\{$',
                'struct': r'^type\s+\w+\s+struct\s*\{$',
                'interface': r'^type\s+\w+\s+interface\s*\{$',
                'import': r'^(import\s+.*|package\s+.*)$'
            }
        }
    
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
        
        # 添加代码结构分析
        structure = self._analyze_code_structure(content, language)
        if structure:
            markdown += "## 代码结构\n\n"
            for item in structure:
                markdown += f"- {item}\n"
            markdown += "\n"
        
        return markdown
    
    def _analyze_code_structure(self, content: str, language: str) -> List[str]:
        """分析代码结构"""
        structure = []
        lines = content.split('\n')
        
        if language not in self.language_patterns:
            return structure
        
        patterns = self.language_patterns[language]
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('//'):
                continue
            
            for pattern_type, pattern in patterns.items():
                if re.match(pattern, line, re.MULTILINE):
                    structure.append(f"{pattern_type.title()} (行 {i}): {line[:50]}{'...' if len(line) > 50 else ''}")
                    break
        
        return structure
    
    def split_code_intelligently(self, content: str, language: str, max_chunk_size: int = 2000) -> List[str]:
        """智能分割代码，确保分割点在代码块边界"""
        lines = content.split('\n')
        chunks = []
        current_chunk = []
        current_size = 0
        
        # 代码块边界检测
        def is_code_boundary(line: str, language: str) -> bool:
            line = line.strip()
            if not line:
                return True
            
            # 通用边界模式
            if line.startswith('#') or line.startswith('//'):
                return True
            
            if language in self.language_patterns:
                patterns = self.language_patterns[language]
                for pattern in patterns.values():
                    if re.match(pattern, line):
                        return True
            
            # 检查缩进变化（函数/类结束）
            if language == 'python':
                if line and not line.startswith(' ') and not line.startswith('\t'):
                    return True
            
            return False
        
        for i, line in enumerate(lines):
            line_size = len(line) + 1  # +1 for newline
            
            # 如果添加这行会超过限制，且当前位置是边界，则分割
            if (current_size + line_size > max_chunk_size and 
                current_chunk and 
                is_code_boundary(line, language)):
                
                chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
                current_size = line_size
            else:
                current_chunk.append(line)
                current_size += line_size
        
        # 添加最后一个chunk
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        return [chunk for chunk in chunks if chunk.strip()]
    
    def get_supported_extensions(self) -> List[str]:
        return self.supported_extensions