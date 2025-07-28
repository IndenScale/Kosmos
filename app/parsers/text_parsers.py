"""
文本文件解析器
文件: text_parsers.py
创建时间: 2025-07-26
描述: 实现纯文本、Markdown、代码文件等的解析器，集成智能文本分割器
"""

import re
from typing import List, Dict, Any
from pathlib import Path

from app.parsers.base_parser import DocumentParser, ParsedFragment
from app.parsers.parser_utils import url_to_local_path
from app.schemas.fragment import FragmentType
from app.utils.text_splitter import TextSplitter


class PlainTextParser(DocumentParser):
    """普通文本解析器"""

    def can_parse(self, file_path: str, mime_type: str) -> bool:
        """判断是否可以解析该文件"""
        local_path = url_to_local_path(file_path)
        return mime_type == 'text/plain' or Path(local_path).suffix.lower() in ['.txt', '.log']

    def parse(self, file_path: str) -> List[ParsedFragment]:
        """解析普通文本文件"""
        # 转换URL为本地路径
        local_path = url_to_local_path(file_path)

        try:
            with open(local_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # 尝试其他编码
            try:
                with open(local_path, 'r', encoding='gbk') as f:
                    content = f.read()
            except UnicodeDecodeError:
                with open(local_path, 'r', encoding='latin-1') as f:
                    content = f.read()

        if not content.strip():
            return []

        # 使用智能文本分割器
        try:
            splitter = TextSplitter(chunk_size=1350, chunk_overlap=150)
            chunks = splitter.split_text(content)
            split_method = "intelligent"
        except Exception as e:
            self.logger.warning(f"智能文本分割失败，使用传统方法: {e}")
            chunks = self._split_text(content)
            split_method = "traditional"

        fragments = []
        for i, chunk in enumerate(chunks):
            meta_info = self._create_meta_info(
                content_length=len(chunk),
                chunk_index=i,
                total_chunks=len(chunks),
                file_encoding="utf-8",
                split_method='intelligent_splitter' if 'splitter' in locals() else 'traditional',
                page_start=1,
                page_end=1
            )

            fragment = ParsedFragment(
                fragment_type=FragmentType.TEXT,
                raw_content=chunk,
                meta_info=meta_info,
                fragment_index=i
            )
            fragments.append(fragment)

        return fragments


class MarkdownParser(DocumentParser):
    """Markdown解析器"""

    def can_parse(self, file_path: str, mime_type: str) -> bool:
        """判断是否可以解析该文件"""
        local_path = url_to_local_path(file_path)
        return (mime_type == 'text/markdown' or
                Path(local_path).suffix.lower() in ['.md', '.markdown'])

    def parse(self, file_path: str) -> List[ParsedFragment]:
        """解析Markdown文件"""
        # 转换URL为本地路径
        local_path = url_to_local_path(file_path)

        try:
            with open(local_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(local_path, 'r', encoding='gbk') as f:
                content = f.read()

        if not content.strip():
            return []

        # 按标题分割Markdown内容
        sections = self._split_markdown_by_headers(content)

        fragments = []
        for i, section in enumerate(sections):
            if not section['content'].strip():
                continue

            # 如果section内容过长，使用智能分割器进一步分割
            if len(section['content']) > 1500:
                sub_fragments = self._split_text_with_intelligent_splitter(
                    section['content'], i, section
                )
                fragments.extend(sub_fragments)
            else:
                meta_info = self._create_meta_info(
                    content_length=len(section['content']),
                    header_level=section['level'],
                    header_title=section['title'],
                    section_index=i,
                    total_sections=len(sections),
                    page_start=1,
                    page_end=1
                )

                fragment = ParsedFragment(
                    fragment_type=FragmentType.TEXT,
                    raw_content=section['content'],
                    meta_info=meta_info,
                    fragment_index=len(fragments)
                )
                fragments.append(fragment)

        return fragments

    def _split_text_with_intelligent_splitter(self, text: str, section_index: int, section: Dict[str, Any]) -> List[ParsedFragment]:
        """使用智能文本分割器分割文本"""
        try:
            splitter = TextSplitter(chunk_size=1350, chunk_overlap=150)

            chunks = splitter.split_text(text)
            fragments = []

            for i, chunk in enumerate(chunks):
                meta_info = self._create_meta_info(
                    content_length=len(chunk),
                    header_level=section['level'],
                    header_title=section['title'],
                    section_index=section_index,
                    chunk_index=i,
                    total_chunks=len(chunks),
                    split_method='intelligent_splitter',
                    page_start=1,
                    page_end=1
                )

                fragment = ParsedFragment(
                    fragment_type=FragmentType.TEXT,
                    raw_content=chunk,
                    meta_info=meta_info,
                    fragment_index=len(fragments)
                )
                fragments.append(fragment)

            return fragments

        except Exception as e:
            self.logger.warning(f"智能分割失败，使用原始内容: {e}")
            # 回退到原始方法
            meta_info = self._create_meta_info(
                content_length=len(text),
                header_level=section['level'],
                header_title=section['title'],
                section_index=section_index,
                split_method='fallback',
                page_start=1,
                page_end=1
            )

            fragment = ParsedFragment(
                fragment_type=FragmentType.TEXT,
                raw_content=text,
                meta_info=meta_info,
                fragment_index=0
            )
            return [fragment]

    def _split_markdown_by_headers(self, content: str) -> List[Dict[str, Any]]:
        """按标题分割Markdown内容"""
        lines = content.split('\n')
        sections = []
        current_section = {'level': 0, 'title': '', 'content': ''}

        for line in lines:
            # 检查是否是标题行
            header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if header_match:
                # 保存当前section
                if current_section['content'].strip():
                    sections.append(current_section.copy())

                # 开始新section
                level = len(header_match.group(1))
                title = header_match.group(2).strip()
                current_section = {
                    'level': level,
                    'title': title,
                    'content': line + '\n'
                }
            else:
                current_section['content'] += line + '\n'

        # 添加最后一个section
        if current_section['content'].strip():
            sections.append(current_section)

        # 如果没有找到标题，将整个内容作为一个section
        if not sections:
            # 使用传入的file_path参数获取文件名
            local_path = url_to_local_path(file_path) if 'file_path' in locals() else 'Document'
            sections.append({
                'level': 0,
                'title': Path(local_path).stem if local_path != 'Document' else 'Document',
                'content': content
            })

        return sections


class CodeParser(DocumentParser):
    """代码文件解析器"""

    def can_parse(self, file_path: str, mime_type: str) -> bool:
        """判断是否可以解析该文件"""
        code_mimes = [
            'text/x-python', 'text/javascript', 'text/typescript',
            'text/x-c', 'text/x-c++', 'text/x-java', 'text/x-csharp',
            'text/x-php', 'text/x-ruby', 'text/x-go', 'text/x-rust',
            'text/x-sql', 'text/x-shellscript'
        ]

        code_exts = [
            '.py', '.js', '.ts', '.jsx', '.tsx', '.vue', '.java', '.c', '.cpp',
            '.h', '.hpp', '.cs', '.php', '.rb', '.go', '.rs', '.sql', '.sh',
            '.bat', '.ps1', '.r', '.scala', '.kt', '.swift', '.dart', '.lua'
        ]

        local_path = url_to_local_path(file_path)
        return (mime_type in code_mimes or
                Path(local_path).suffix.lower() in code_exts)

    def parse(self, file_path: str) -> List[ParsedFragment]:
        """解析代码文件"""
        # 转换URL为本地路径
        local_path = url_to_local_path(file_path)

        try:
            with open(local_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(local_path, 'r', encoding='gbk') as f:
                content = f.read()

        if not content.strip():
            return []

        # 获取编程语言
        language = self._detect_language(file_path)

        # 按函数/类分割代码
        code_blocks = self._split_code_by_structure(content, language)

        fragments = []
        for i, block in enumerate(code_blocks):
            meta_info = self._create_meta_info(
                content_length=len(block['content']),
                language=language,
                block_type=block['type'],
                block_name=block['name'],
                start_line=block['start_line'],
                end_line=block['end_line'],
                block_index=i,
                total_blocks=len(code_blocks),
                page_start=1,
                page_end=1
            )

            fragment = ParsedFragment(
                fragment_type=FragmentType.TEXT,
                raw_content=block['content'],
                meta_info=meta_info,
                fragment_index=i
            )
            fragments.append(fragment)

        return fragments

    def _detect_language(self, file_path: str) -> str:
        """检测编程语言"""
        local_path = url_to_local_path(file_path)
        ext = Path(local_path).suffix.lower()

        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'javascript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.c': 'c',
            '.cpp': 'cpp',
            '.h': 'c',
            '.hpp': 'cpp',
            '.cs': 'csharp',
            '.php': 'php',
            '.rb': 'ruby',
            '.go': 'go',
            '.rs': 'rust',
            '.sql': 'sql',
            '.sh': 'bash',
            '.bat': 'batch',
            '.ps1': 'powershell',
        }

        return language_map.get(ext, 'text')

    def _split_code_by_structure(self, content: str, language: str) -> List[Dict[str, Any]]:
        """按代码结构分割（函数、类等）"""
        lines = content.split('\n')
        blocks = []

        if language == 'python':
            blocks = self._split_python_code(lines)
        elif language in ['javascript', 'typescript']:
            blocks = self._split_js_code(lines)
        elif language == 'java':
            blocks = self._split_java_code(lines)
        else:
            # 对于其他语言，简单按行数分割
            blocks = self._split_code_by_lines(lines, max_lines=50)

        return blocks

    def _split_python_code(self, lines: List[str]) -> List[Dict[str, Any]]:
        """分割Python代码"""
        blocks = []
        current_block = {'type': 'module', 'name': '', 'start_line': 1, 'lines': []}

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # 检查类定义
            if stripped.startswith('class '):
                if current_block['lines']:
                    current_block['end_line'] = i - 1
                    current_block['content'] = '\n'.join(current_block['lines'])
                    blocks.append(current_block)

                class_name = stripped.split('(')[0].replace('class ', '').strip(':')
                current_block = {
                    'type': 'class',
                    'name': class_name,
                    'start_line': i,
                    'lines': [line]
                }

            # 检查函数定义
            elif stripped.startswith('def '):
                if current_block['lines'] and current_block['type'] != 'class':
                    current_block['end_line'] = i - 1
                    current_block['content'] = '\n'.join(current_block['lines'])
                    blocks.append(current_block)

                    func_name = stripped.split('(')[0].replace('def ', '').strip()
                    current_block = {
                        'type': 'function',
                        'name': func_name,
                        'start_line': i,
                        'lines': [line]
                    }
                else:
                    current_block['lines'].append(line)
            else:
                current_block['lines'].append(line)

        # 添加最后一个块
        if current_block['lines']:
            current_block['end_line'] = len(lines)
            current_block['content'] = '\n'.join(current_block['lines'])
            blocks.append(current_block)

        return blocks

    def _split_js_code(self, lines: List[str]) -> List[Dict[str, Any]]:
        """分割JavaScript/TypeScript代码"""
        # 简化实现，按函数分割
        blocks = []
        current_block = {'type': 'module', 'name': '', 'start_line': 1, 'lines': []}

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # 检查函数定义
            if (stripped.startswith('function ') or
                'function(' in stripped or
                '=>' in stripped):

                if current_block['lines']:
                    current_block['end_line'] = i - 1
                    current_block['content'] = '\n'.join(current_block['lines'])
                    blocks.append(current_block)

                current_block = {
                    'type': 'function',
                    'name': self._extract_js_function_name(stripped),
                    'start_line': i,
                    'lines': [line]
                }
            else:
                current_block['lines'].append(line)

        # 添加最后一个块
        if current_block['lines']:
            current_block['end_line'] = len(lines)
            current_block['content'] = '\n'.join(current_block['lines'])
            blocks.append(current_block)

        return blocks

    def _split_java_code(self, lines: List[str]) -> List[Dict[str, Any]]:
        """分割Java代码"""
        # 简化实现，按类和方法分割
        return self._split_code_by_lines(lines, max_lines=50)

    def _split_code_by_lines(self, lines: List[str], max_lines: int = 50) -> List[Dict[str, Any]]:
        """按行数分割代码"""
        blocks = []

        for i in range(0, len(lines), max_lines):
            end_idx = min(i + max_lines, len(lines))
            block_lines = lines[i:end_idx]

            blocks.append({
                'type': 'code_block',
                'name': f'Block {i//max_lines + 1}',
                'start_line': i + 1,
                'end_line': end_idx,
                'content': '\n'.join(block_lines),
                'lines': block_lines
            })

        return blocks

    def _extract_js_function_name(self, line: str) -> str:
        """提取JavaScript函数名"""
        # 简化实现
        if 'function ' in line:
            parts = line.split('function ')[1].split('(')[0].strip()
            return parts
        elif '=>' in line:
            parts = line.split('=>')[0].strip()
            if '=' in parts:
                return parts.split('=')[0].strip()
        return 'anonymous'