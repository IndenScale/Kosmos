import re
from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class ParsedQuery:
    """解析后的查询对象"""
    text: str
    must_tags: List[str]
    must_not_tags: List[str]
    like_tags: List[str]
    original_query: str

class QueryParser:
    """查询解析器，支持标签语法：' +tag'（必须有）、' -tag'（必须没有）、' ~tag'（偏好）"""
    
    def parse(self, query: str) -> ParsedQuery:
        """
        解析复合查询字符串
        
        语法规则：
        - 第一个分隔符之前的内容作为文本查询
        - ' +tag' 表示必须包含的标签（注意前面必须有空格）
        - ' -tag' 表示必须不包含的标签（注意前面必须有空格）
        - ' ~tag' 表示偏好标签（注意前面必须有空格）
        
        示例：
        - "AI发展 +技术 -历史 ~应用" -> text="AI发展", must_tags=["技术"], must_not_tags=["历史"], like_tags=["应用"]
        - "机器学习算法 +深度学习 +神经网络" -> text="机器学习算法", must_tags=["深度学习", "神经网络"]
        """
        original_query = query
        query = query.strip()
        
        if not query:
            return ParsedQuery("", [], [], [], original_query)
        
        # 使用正则表达式匹配标签模式
        # 匹配 ' +tag'、' -tag'、' ~tag' 模式（注意前面必须有空格）
        tag_pattern = r'(\s+[+\-~]\S+)'
        
        # 分割查询字符串
        parts = re.split(tag_pattern, query)
        
        # 第一部分是文本查询
        text_query = parts[0].strip() if parts else ""
        
        must_tags = []
        must_not_tags = []
        like_tags = []
        
        # 解析标签部分
        for part in parts[1:]:
            part = part.strip()
            if not part:
                continue
                
            if part.startswith('+'):
                tag = part[1:].strip()
                if tag:
                    must_tags.append(tag)
            elif part.startswith('-'):
                tag = part[1:].strip()
                if tag:
                    must_not_tags.append(tag)
            elif part.startswith('~'):
                tag = part[1:].strip()
                if tag:
                    like_tags.append(tag)
        
        return ParsedQuery(text_query, must_tags, must_not_tags, like_tags, original_query)
    
    def format_parse_result(self, parsed: ParsedQuery) -> Dict[str, Any]:
        """格式化解析结果为字典"""
        return {
            "text_query": parsed.text,
            "must_tags": parsed.must_tags,
            "must_not_tags": parsed.must_not_tags,
            "like_tags": parsed.like_tags,
            "original_query": parsed.original_query
        }