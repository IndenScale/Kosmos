"""
分页工具模块
提供基于光标的分页功能
"""

import base64
from datetime import datetime
from typing import Dict, List, Any, Optional


def encode_cursor(cursor_time: datetime) -> str:
    """
    将时间编码为游标字符串
    
    Args:
        cursor_time: 时间对象
        
    Returns:
        base64编码的游标字符串
    """
    return base64.urlsafe_b64encode(cursor_time.isoformat().encode()).decode()


def decode_cursor(cursor: str) -> Optional[datetime]:
    """
    解码游标字符串为时间对象
    
    Args:
        cursor: base64编码的游标字符串
        
    Returns:
        解码后的时间对象，如果解码失败则返回None
    """
    try:
        cursor_time_str = base64.urlsafe_b64decode(cursor).decode()
        return datetime.fromisoformat(cursor_time_str)
    except (ValueError, TypeError):
        return None


def create_paginated_response(
    items: List[Any],
    page_size: int,
    get_cursor_func = lambda item: item.created_at
) -> Dict[str, Any]:
    """
    创建分页响应
    
    Args:
        items: 当前页的项目列表
        page_size: 每页大小
        get_cursor_func: 获取项目游标值的函数，默认为获取created_at
        
    Returns:
        包含items和next_cursor的字典
    """
    next_cursor = None
    if len(items) > page_size:
        next_item = items[page_size]
        next_cursor = encode_cursor(get_cursor_func(next_item))
        items = items[:page_size]

    return {"items": items, "next_cursor": next_cursor}