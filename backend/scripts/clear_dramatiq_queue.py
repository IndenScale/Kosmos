#!/usr/bin/env python3
"""
清理Dramatiq消息队列的脚本
用于废弃启动前的所有待处理任务
"""
import redis
import sys
import os
from pathlib import Path

# 添加backend目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.core.config import settings

def clear_dramatiq_queues():
    """清空所有Dramatiq相关的Redis队列"""
    try:
        # 连接到Redis
        r = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True
        )
        
        # 需要清理的队列键模式
        queue_patterns = [
            "dramatiq:default",           # 默认队列
            "dramatiq:default.XT",        # 延迟队列
            "dramatiq:default.DQ",        # 死信队列
            "dramatiq:__heartbeats__",    # 心跳
            "dramatiq:__failed__",        # 失败消息
        ]
        
        deleted_keys = []
        
        # 删除匹配的键
        for pattern in queue_patterns:
            keys = r.keys(f"{pattern}*")
            for key in keys:
                r.delete(key)
                deleted_keys.append(key)
        
        print(f"已清理 {len(deleted_keys)} 个Dramatiq相关键")
        for key in deleted_keys:
            print(f"  - 删除: {key}")
            
        return True
        
    except Exception as e:
        print(f"清理队列时出错: {e}")
        return False

if __name__ == "__main__":
    print("开始清理Dramatiq消息队列...")
    success = clear_dramatiq_queues()
    if success:
        print("队列清理完成！")
    else:
        print("队列清理失败！")
        sys.exit(1)