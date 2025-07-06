import re
from typing import List

class TextSplitter:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._json_splitter = None
    
    def split_text(self, text: str) -> List[str]:
        """将文本分割成chunks，保持页码标记与内容的关联"""
        if not text.strip():
            return []
        
        # 检查是否是JSON内容，如果是则使用专门的JSON分割器
        if self._is_json_content(text):
            return self._split_json_content(text)
        
        # 首先按页面分割
        page_sections = self._split_by_pages(text)
        
        if not page_sections:
            # 如果没有页码标记，使用传统方法
            return self._traditional_split(text)
        
        chunks = []
        
        for page_section in page_sections:
            # 每个页面可能还需要进一步分割
            page_chunks = self._split_page_section(page_section)
            chunks.extend(page_chunks)
        
        return [chunk for chunk in chunks if chunk.strip()]
    
    def _split_by_pages(self, text: str) -> List[str]:
        """按页码标记分割文本"""
        # 查找页码标记模式
        page_pattern = r'##\s*第\d+页'
        
        # 如果没有找到页码标记，返回空列表
        if not re.search(page_pattern, text):
            return []
        
        # 按页码标记分割
        page_sections = re.split(page_pattern, text)
        page_headers = re.findall(page_pattern, text)
        
        # 重新组装，确保每个部分都包含页码标记
        result = []
        
        # 第一个部分可能没有页码标记（文档开头）
        if page_sections[0].strip():
            result.append(page_sections[0].strip())
        
        # 后续部分都有页码标记
        for i, header in enumerate(page_headers):
            section_content = page_sections[i + 1] if i + 1 < len(page_sections) else ""
            combined = f"{header}\n\n{section_content}".strip()
            if combined:
                result.append(combined)
        
        return result
    
    def _split_page_section(self, page_section: str) -> List[str]:
        """分割单个页面的内容，保持页码标记在第一个chunk中"""
        if len(page_section) <= self.chunk_size:
            return [page_section]
        
        # 提取页码标记
        page_header_match = re.match(r'(##\s*第\d+页)', page_section)
        page_header = page_header_match.group(1) if page_header_match else ""
        
        # 获取页面内容（去除页码标记）
        content = page_section[len(page_header):].strip() if page_header else page_section
        
        # 分割内容
        content_chunks = self._traditional_split(content)
        
        # 将页码标记添加到第一个chunk
        if content_chunks and page_header:
            content_chunks[0] = f"{page_header}\n\n{content_chunks[0]}"
        
        return content_chunks
    
    def _traditional_split(self, text: str) -> List[str]:
        """传统的文本分割方法"""
        # 按段落分割
        paragraphs = self._split_by_paragraphs(text)
        
        chunks = []
        current_chunk = ""
        
        for paragraph in paragraphs:
            # 如果当前段落加上现有chunk超过大小限制
            if len(current_chunk) + len(paragraph) > self.chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    # 保留重叠部分
                    current_chunk = self._get_overlap(current_chunk)
                
                # 如果单个段落就超过限制，需要进一步分割
                if len(paragraph) > self.chunk_size:
                    sub_chunks = self._split_long_paragraph(paragraph)
                    for i, sub_chunk in enumerate(sub_chunks):
                        if i == 0 and current_chunk:
                            current_chunk += "\n\n" + sub_chunk
                        else:
                            if current_chunk:
                                chunks.append(current_chunk.strip())
                            current_chunk = sub_chunk
                else:
                    current_chunk += "\n\n" + paragraph if current_chunk else paragraph
            else:
                current_chunk += "\n\n" + paragraph if current_chunk else paragraph
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return [chunk for chunk in chunks if chunk.strip()]
    
    def _split_by_paragraphs(self, text: str) -> List[str]:
        """按段落分割文本"""
        # 按双换行符分割段落
        paragraphs = re.split(r'\n\s*\n', text)
        return [p.strip() for p in paragraphs if p.strip()]
    
    def _split_long_paragraph(self, paragraph: str) -> List[str]:
        """分割过长的段落"""
        # 按句子分割
        sentences = re.split(r'[.!?。！？]\s+', paragraph)
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) > self.chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = self._get_overlap(current_chunk)
                current_chunk += sentence
            else:
                current_chunk += sentence + ". " if current_chunk else sentence
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _get_overlap(self, text: str) -> str:
        """获取重叠部分"""
        if len(text) <= self.chunk_overlap:
            return text
        return text[-self.chunk_overlap:]
    
    def _is_json_content(self, text: str) -> bool:
        """检查是否是JSON内容"""
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
    
    def _split_json_content(self, text: str) -> List[str]:
        """使用专门的JSON分割器分割JSON内容"""
        if self._json_splitter is None:
            # 延迟导入避免循环依赖
            from .json_text_splitter import JsonTextSplitter
            self._json_splitter = JsonTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap
            )
        
        return self._json_splitter.split_text(text)