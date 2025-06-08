from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class ParsedQuery:
    """解析后的查询对象"""
    text: str
    must_tags: List[str]
    must_not_tags: List[str]
    like_tags: List[str]

class QueryParser:
    """查询解析器"""
    
    def parse(self, query: str) -> ParsedQuery:
        """解析复合查询字符串"""
        parts = query.strip().split()
        
        if not parts:
            return ParsedQuery("", [], [], [])
        
        # 第一个部分作为文本查询
        text = parts[0]
        
        must_tags = []
        must_not_tags = []
        like_tags = []
        
        # 解析剩余部分的标签
        for part in parts[1:]:
            if part.startswith("+"):
                must_tags.append(part[1:])
            elif part.startswith("-"):
                must_not_tags.append(part[1:])
            elif part.startswith("~"):
                like_tags.append(part[1:])
            else:
                # 无前缀默认为like_tags
                like_tags.append(part)
        
        return ParsedQuery(text, must_tags, must_not_tags, like_tags)