from typing import List, Dict, Any

class IntelligentTextSplitter:
    """
    智能文本分割器，用于将结构化的内容块合并成语义完整的chunks。
    保证原子块（如图片描述）不会被分割。
    """
    def __init__(self, max_chunk_size: int = 2048, min_chunk_size: int = 128):
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size

    def split(self, blocks: List[Dict[str, Any]]) -> List[str]:
        """
        将结构化内容块列表分割成最终的chunks (v2 - 智能合并逻辑)。
        
        Args:
            blocks: 内容块列表。
        
        Returns:
            最终的chunks列表。
        """
        chunks = []
        current_chunk_blocks = []
        current_length = 0

        for block in blocks:
            block_md = self._format_block_to_markdown(block).strip()
            if not block_md:
                continue
            
            block_len = len(block_md)
            
            # 检查加上新块是否会超长
            # (+2 是为了换行符)
            would_exceed = current_length > 0 and (current_length + 2 + block_len > self.max_chunk_size)
            
            # 当前块是否太小而不能独立成块
            is_too_small = current_length > 0 and current_length < self.min_chunk_size
            
            if would_exceed:
                # 如果当前块太小，则强制合并，即使会超长
                if is_too_small:
                    current_chunk_blocks.append(block)
                    chunks.append(self._format_blocks_to_chunk(current_chunk_blocks))
                    current_chunk_blocks = []
                    current_length = 0
                # 否则，当前块长度足够，可以独立成块
                else:
                    chunks.append(self._format_blocks_to_chunk(current_chunk_blocks))
                    current_chunk_blocks = [block]
                    current_length = block_len
            else:
                # 如果没超长，直接添加
                current_chunk_blocks.append(block)
                current_length += block_len + (2 if len(current_chunk_blocks) > 1 else 0)

        # 不要忘记最后一个chunk
        if current_chunk_blocks:
            chunks.append(self._format_blocks_to_chunk(current_chunk_blocks))
            
        return chunks

    def _format_blocks_to_chunk(self, blocks: List[Dict[str, Any]]) -> str:
        """将一组内容块格式化为单个Markdown字符串"""
        return "\n\n".join([self._format_block_to_markdown(b) for b in blocks])

    def _format_block_to_markdown(self, block: Dict[str, Any]) -> str:
        """将单个内容块格式化为Markdown字符串"""
        block_type = block.get('type')
        content = block.get('content', '')
        
        if block_type == 'heading':
            level = block.get('level', 1)
            return f"{'#' * level} {content}"
        elif block_type == 'text':
            return content
        elif block_type == 'image_description':
            return content
        else:
            return content

    def _merge_small_chunks(self, chunks: List[str]) -> List[str]:
        """合并过小的chunks，以提高上下文的连贯性"""
        if not chunks:
            return []

        merged_chunks = []
        temp_chunk = chunks[0]

        for i in range(1, len(chunks)):
            next_chunk = chunks[i]
            # 如果当前chunk太小，并且合并后不超长，则合并
            if len(temp_chunk) < self.min_chunk_size and \
               len(temp_chunk) + len(next_chunk) <= self.max_chunk_size:
                temp_chunk += "\n\n" + next_chunk
            else:
                merged_chunks.append(temp_chunk)
                temp_chunk = next_chunk
        
        # 添加最后一个chunk
        merged_chunks.append(temp_chunk)
        
        return merged_chunks 