#!/usr/bin/env python3
"""
测试 result_dict 修复
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.models.job import Task
from app.schemas.job import TaskResponse
from app.models.job import TaskType, TaskStatus, TargetType

def test_result_dict_fix():
    """测试 result_dict 修复"""
    
    # 创建一个 Task 实例
    task = Task()
    task.id = "test-task-id"
    task.job_id = "test-job-id"
    task.task_type = TaskType.PARSE_DOCUMENT.value
    task.status = TaskStatus.COMPLETED.value
    task.target_id = "test-doc-id"
    task.target_type = TargetType.DOCUMENT.value
    task.worker_id = "test-worker"
    task.retry_count = 0
    task.max_retries = 3
    task.error_message = None
    
    # 测试不同类型的 result 值
    test_cases = [
        # 有效的 JSON 字典
        '{"document_id": "7f00baa", "status": "success", "parse_duration_ms": 23}',
        # 有效的 JSON 但不是字典
        '"simple string"',
        # 无效的 JSON
        "{'document_id': '7f00baa', 'status': 'success', 'parse_duration_ms': 23}",
        # 空值
        None,
        # 空字符串
        "",
    ]
    
    for i, result_value in enumerate(test_cases):
        print(f"\n测试用例 {i + 1}: {result_value}")
        
        # 设置 result 值
        task.result = result_value
        
        try:
            # 获取 result_dict
            result_dict = task.result_dict
            print(f"result_dict: {result_dict}")
            print(f"类型: {type(result_dict)}")
            
            # 尝试创建 TaskResponse
            task_response = TaskResponse(
                id=task.id,
                job_id=task.job_id,
                task_type=TaskType.PARSE_DOCUMENT,
                status=TaskStatus.COMPLETED,
                target_id=task.target_id,
                target_type=TargetType.DOCUMENT,
                config={},
                worker_id=task.worker_id,
                retry_count=task.retry_count,
                max_retries=task.max_retries,
                result=result_dict,  # 这里应该是字典
                error_message=task.error_message,
                created_at=task.created_at or "2024-01-01T00:00:00",
                updated_at=task.updated_at or "2024-01-01T00:00:00",
                started_at=task.started_at,
                completed_at=task.completed_at
            )
            print(f"TaskResponse 创建成功: {task_response.result}")
            
        except Exception as e:
            print(f"错误: {e}")

if __name__ == "__main__":
    test_result_dict_fix()