import json
import re
from typing import List, Dict, Any, Union
from .text_splitter import TextSplitter


class JsonTextSplitter(TextSplitter):
    """专门用于JSON内容的文本分割器，保持JSON对象的完整性"""
    
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        super().__init__(chunk_size, chunk_overlap)
        self.json_object_patterns = [
            r'## 行 \d+',  # JSONL行标记
            r'### 项目 \d+',  # JSON数组项标记
            r'# [^#\n]+',  # 顶级标题
            r'## [^#\n]+',  # 二级标题
            r'### [^#\n]+',  # 三级标题
            r'#### [^#\n]+',  # 四级标题
        ]
    
    def split_text(self, text: str) -> List[str]:
        """分割JSON格式的文本，保持JSON对象的完整性"""
        if not text.strip():
            return []
        
        # 检查是否是JSON格式的markdown
        if self._is_json_markdown(text):
            return self._split_json_markdown(text)
        else:
            # 回退到传统分割方法
            return super().split_text(text)
    
    def _is_json_markdown(self, text: str) -> bool:
        """检查文本是否为JSON格式的markdown"""
        # 检查是否包含JSON相关的标记
        json_indicators = [
            r'# JSON文件:',
            r'# JSONL文件:',
            r'## 行 \d+',
            r'### 项目 \d+',
            r'```json',
            r'\*\*值:\*\*',
            r'\*\*数组长度:\*\*'
        ]
        
        for pattern in json_indicators:
            if re.search(pattern, text):
                return True
        return False
    
    def _split_json_markdown(self, text: str) -> List[str]:
        """分割JSON格式的markdown文本"""
        # 首先尝试按照JSON对象结构分割
        json_chunks = self._split_by_json_objects(text)
        
        # 如果分割后的块仍然太大，进一步分割
        final_chunks = []
        for chunk in json_chunks:
            if len(chunk) <= self.chunk_size:
                final_chunks.append(chunk)
            else:
                # 对大块进行进一步分割
                sub_chunks = self._split_large_json_chunk(chunk)
                final_chunks.extend(sub_chunks)
        
        return [chunk for chunk in final_chunks if chunk.strip()]
    
    def _split_by_json_objects(self, text: str) -> List[str]:
        """按JSON对象结构分割文本"""
        # 尝试按照不同级别的标题分割
        for pattern in self.json_object_patterns:
            chunks = self._split_by_pattern(text, pattern)
            if len(chunks) > 1:
                return chunks
        
        # 如果没有找到合适的分割点，按段落分割
        return self._split_by_paragraphs(text)
    
    def _split_by_pattern(self, text: str, pattern: str) -> List[str]:
        """按指定模式分割文本"""
        # 查找所有匹配的位置
        matches = list(re.finditer(pattern, text))
        
        if not matches:
            return [text]
        
        chunks = []
        
        # 处理第一个匹配之前的内容
        if matches[0].start() > 0:
            first_chunk = text[:matches[0].start()].strip()
            if first_chunk:
                chunks.append(first_chunk)
        
        # 处理每个匹配的内容
        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
        
        return chunks
    
    def _split_large_json_chunk(self, chunk: str) -> List[str]:
        """分割过大的JSON块"""
        # 尝试按照更细粒度的模式分割
        fine_patterns = [
            r'#### [^#\n]+',  # 四级标题
            r'##### [^#\n]+',  # 五级标题
            r'###### [^#\n]+',  # 六级标题
            r'\*\*项目 \d+:\*\*',  # 项目标记
            r'\*\*值:\*\*',  # 值标记
        ]
        
        for pattern in fine_patterns:
            sub_chunks = self._split_by_pattern(chunk, pattern)
            if len(sub_chunks) > 1:
                # 检查分割后的块是否合适
                suitable_chunks = []
                for sub_chunk in sub_chunks:
                    if len(sub_chunk) <= self.chunk_size:
                        suitable_chunks.append(sub_chunk)
                    else:
                        # 继续分割
                        further_chunks = self._split_by_content_structure(sub_chunk)
                        suitable_chunks.extend(further_chunks)
                return suitable_chunks
        
        # 如果仍然无法分割，按内容结构分割
        return self._split_by_content_structure(chunk)
    
    def _split_by_content_structure(self, text: str) -> List[str]:
        """按内容结构分割文本"""
        # 按代码块和普通文本分离
        code_block_pattern = r'```[^`]*```'
        parts = []
        last_end = 0
        
        for match in re.finditer(code_block_pattern, text, re.DOTALL):
            # 添加代码块前的文本
            if match.start() > last_end:
                before_text = text[last_end:match.start()].strip()
                if before_text:
                    parts.append(before_text)
            
            # 添加代码块
            code_block = match.group(0)
            parts.append(code_block)
            last_end = match.end()
        
        # 添加最后一部分
        if last_end < len(text):
            after_text = text[last_end:].strip()
            if after_text:
                parts.append(after_text)
        
        # 合并小的部分
        return self._merge_small_parts(parts)
    
    def _merge_small_parts(self, parts: List[str]) -> List[str]:
        """合并小的部分"""
        if not parts:
            return []
        
        merged = []
        current_chunk = ""
        
        for part in parts:
            if len(current_chunk) + len(part) + 2 <= self.chunk_size:  # +2 for newlines
                current_chunk += "\n\n" + part if current_chunk else part
            else:
                if current_chunk:
                    merged.append(current_chunk.strip())
                
                if len(part) > self.chunk_size:
                    # 如果单个部分太大，使用传统方法分割
                    traditional_chunks = self._traditional_split(part)
                    merged.extend(traditional_chunks)
                    current_chunk = ""
                else:
                    current_chunk = part
        
        if current_chunk.strip():
            merged.append(current_chunk.strip())
        
        return merged
    
    def _extract_json_objects_from_jsonl(self, jsonl_text: str) -> List[Dict[str, Any]]:
        """从JSONL文本中提取JSON对象"""
        objects = []
        
        # 查找所有的JSON对象
        lines = jsonl_text.split('\n')
        current_object = {}
        
        for line in lines:
            line = line.strip()
            if line.startswith('## 行'):
                # 新的JSON对象开始
                if current_object:
                    objects.append(current_object)
                current_object = {'header': line}
            elif line.startswith('**') and line.endswith('**'):
                # 可能是键值对
                key_match = re.match(r'\*\*([^:]+):\*\*', line)
                if key_match:
                    key = key_match.group(1)
                    current_object[key] = line
            elif line.startswith('```'):
                # 代码块
                if 'code_blocks' not in current_object:
                    current_object['code_blocks'] = []
                current_object['code_blocks'].append(line)
        
        if current_object:
            objects.append(current_object)
        
        return objects
    
    def get_overlap_for_json(self, text: str) -> str:
        """为JSON内容获取重叠部分"""
        # 对于JSON内容，尝试保持完整的标题或对象信息
        lines = text.split('\n')
        
        # 查找最后一个完整的JSON对象或标题
        overlap_lines = []
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i].strip()
            overlap_lines.insert(0, line)
            
            # 如果找到标题或对象开始，就停止
            if any(re.match(pattern, line) for pattern in self.json_object_patterns):
                break
            
            # 限制重叠长度
            if len('\n'.join(overlap_lines)) >= self.chunk_overlap:
                break
        
        return '\n'.join(overlap_lines) 