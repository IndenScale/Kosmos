"""
统一任务系统模型
文件: job.py
创建时间: 2025-07-26
描述: 定义Job和Task模型，支持解析、索引等多种任务类型
"""

import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from app.db.database import Base
from enum import Enum


class JobType(str, Enum):
    """任务类型枚举"""
    PARSE = "parse"                    # 单文档解析
    INDEX = "index"                    # 单文档索引
    BATCH_PARSE = "batch_parse"        # 批量文档解析
    BATCH_INDEX = "batch_index"        # 批量文档索引
    FULL_REINDEX = "full_reindex"      # 全量重新索引


class JobStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"      # 等待执行
    RUNNING = "running"      # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 失败
    CANCELLED = "cancelled"  # 已取消


class TaskType(str, Enum):
    """具体任务类型枚举"""
    PARSE_DOCUMENT = "parse_document"           # 解析单个文档
    INDEX_FRAGMENT = "index_fragment"           # 索引单个片段
    PARSE_AND_INDEX_DOCUMENT = "parse_and_index_document"  # 解析并索引单个文档
    BATCH_PARSE_DOCUMENTS = "batch_parse_documents"  # 批量解析文档
    BATCH_INDEX_FRAGMENTS = "batch_index_fragments"  # 批量索引片段


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"      # 等待执行
    RUNNING = "running"      # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 失败
    CANCELLED = "cancelled"  # 已取消


class TargetType(str, Enum):
    """任务目标类型枚举"""
    DOCUMENT = "document"
    FRAGMENT = "fragment"


class Job(Base):
    """任务作业模型 - 高层级的业务任务"""
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    kb_id = Column(String, ForeignKey("knowledge_bases.id"), nullable=False)
    job_type = Column(String, nullable=False)  # JobType
    status = Column(String, nullable=False, default=JobStatus.PENDING.value)
    priority = Column(Integer, nullable=False, default=0)

    # 任务配置 (JSON)
    config = Column(Text, nullable=True)

    # 进度跟踪
    total_tasks = Column(Integer, default=0)
    completed_tasks = Column(Integer, default=0)
    failed_tasks = Column(Integer, default=0)

    # 错误信息
    error_message = Column(Text, nullable=True)

    # 时间戳
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # 创建者
    created_by = Column(String, ForeignKey("users.id"), nullable=True)

    # 关系
    tasks = relationship("Task", back_populates="job", cascade="all, delete-orphan")

    @hybrid_property
    def config_dict(self) -> Dict[str, Any]:
        """获取配置字典"""
        if self.config:
            try:
                return json.loads(self.config)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    @config_dict.setter
    def config_dict(self, value: Dict[str, Any]):
        """设置配置字典"""
        self.config = json.dumps(value, ensure_ascii=False) if value else None

    @property
    def progress_percentage(self) -> float:
        """计算进度百分比"""
        if self.total_tasks == 0:
            return 0.0
        return (self.completed_tasks / self.total_tasks) * 100

    @property
    def is_finished(self) -> bool:
        """检查任务是否已结束"""
        return self.status in [JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value]

    def update_progress(self):
        """更新任务进度"""
        completed = sum(1 for task in self.tasks if task.status == TaskStatus.COMPLETED.value)
        failed = sum(1 for task in self.tasks if task.status == TaskStatus.FAILED.value)

        self.completed_tasks = completed
        self.failed_tasks = failed

        # 更新任务状态
        if self.total_tasks > 0:
            if completed + failed == self.total_tasks:
                if failed == 0:
                    self.status = JobStatus.COMPLETED.value
                    self.completed_at = func.now()
                else:
                    self.status = JobStatus.FAILED.value
                    self.completed_at = func.now()


class Task(Base):
    """任务模型 - 具体的执行单元"""
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False)
    task_type = Column(String, nullable=False)  # TaskType
    status = Column(String, nullable=False, default=TaskStatus.PENDING.value)

    # 任务目标
    target_id = Column(String, nullable=True)  # document_id 或 fragment_id
    target_type = Column(String, nullable=True)  # TargetType

    # 任务配置 (JSON)
    config = Column(Text, nullable=True)

    # 执行信息
    worker_id = Column(String, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    # 结果
    result = Column(Text, nullable=True)  # JSON格式的执行结果
    error_message = Column(Text, nullable=True)

    # 时间戳
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # 关系
    job = relationship("Job", back_populates="tasks")

    @hybrid_property
    def config_dict(self) -> Dict[str, Any]:
        """获取配置字典"""
        if self.config:
            try:
                return json.loads(self.config)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    @config_dict.setter
    def config_dict(self, value: Dict[str, Any]):
        """设置配置字典"""
        self.config = json.dumps(value, ensure_ascii=False) if value else None

    @hybrid_property
    def result_dict(self) -> Dict[str, Any]:
        """获取结果字典"""
        if self.result:
            try:
                parsed = json.loads(self.result)
                # 确保返回的是字典
                if isinstance(parsed, dict):
                    return parsed
                else:
                    # 如果解析出来的不是字典，包装成字典
                    return {"value": parsed}
            except (json.JSONDecodeError, TypeError):
                # 如果无法解析为 JSON，将原始字符串包装成字典
                return {"raw_result": self.result}
        return {}

    @result_dict.setter
    def result_dict(self, value: Dict[str, Any]):
        """设置结果字典"""
        self.result = json.dumps(value, ensure_ascii=False) if value else None

    @property
    def can_retry(self) -> bool:
        """检查是否可以重试"""
        return self.retry_count < self.max_retries and self.status == TaskStatus.FAILED.value

    def mark_started(self, worker_id: str):
        """标记任务开始执行"""
        self.status = TaskStatus.RUNNING.value
        self.worker_id = worker_id
        self.started_at = func.now()

    def mark_completed(self, result: Optional[Dict[str, Any]] = None):
        """标记任务完成"""
        self.status = TaskStatus.COMPLETED.value
        self.completed_at = func.now()
        if result:
            self.result_dict = result

    def mark_failed(self, error_message: str, can_retry: bool = True):
        """标记任务失败"""
        self.error_message = error_message
        self.completed_at = func.now()

        if can_retry and self.can_retry:
            self.retry_count += 1
            self.status = TaskStatus.PENDING.value  # 重新排队
            self.started_at = None
            self.completed_at = None
            self.worker_id = None
        else:
            self.status = TaskStatus.FAILED.value