"""
统一任务系统的Pydantic模式
文件: job.py
创建时间: 2025-07-26
描述: 定义统一任务系统的请求和响应模式
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from app.models.job import JobType, JobStatus, TaskType, TaskStatus, TargetType


# 请求模式
class CreateParseJobRequest(BaseModel):
    """创建解析任务请求"""
    kb_id: str = Field(..., description="知识库ID")
    document_ids: List[str] = Field(..., description="文档ID列表")
    priority: int = Field(default=0, description="任务优先级")
    config: Optional[Dict[str, Any]] = Field(default=None, description="任务配置")


class CreateIndexJobRequest(BaseModel):
    """创建索引任务请求"""
    kb_id: str = Field(..., description="知识库ID")
    fragment_ids: List[str] = Field(..., description="片段ID列表")
    priority: int = Field(default=0, description="任务优先级")
    config: Optional[Dict[str, Any]] = Field(default=None, description="任务配置")


class CreateBatchJobRequest(BaseModel):
    """创建批量任务请求"""
    kb_id: str = Field(..., description="知识库ID")
    job_type: JobType = Field(..., description="任务类型")
    target_ids: List[str] = Field(..., description="目标ID列表")
    priority: int = Field(default=0, description="任务优先级")
    config: Optional[Dict[str, Any]] = Field(default=None, description="任务配置")


# 响应模式
class TaskResponse(BaseModel):
    """任务响应"""
    id: str
    job_id: str
    task_type: TaskType
    status: TaskStatus
    target_id: Optional[str]
    target_type: Optional[TargetType]
    config: Optional[Dict[str, Any]]
    worker_id: Optional[str]
    retry_count: int
    max_retries: int
    result: Optional[Dict[str, Any]]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class JobResponse(BaseModel):
    """任务作业响应"""
    id: str
    kb_id: str
    job_type: JobType
    status: JobStatus
    priority: int
    config: Optional[Dict[str, Any]]
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    progress_percentage: float
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_by: Optional[str]

    class Config:
        from_attributes = True


class JobDetailResponse(BaseModel):
    """任务作业详情响应"""
    id: str
    kb_id: str
    job_type: JobType
    status: JobStatus
    priority: int
    config: Optional[Dict[str, Any]]
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    progress_percentage: float
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_by: Optional[str]
    tasks: List[TaskResponse]

    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    """任务作业列表响应"""
    jobs: List[JobResponse]
    total: int
    page: int
    page_size: int


class JobStatsResponse(BaseModel):
    """任务统计响应"""
    total_jobs: int
    pending_jobs: int
    running_jobs: int
    completed_jobs: int
    failed_jobs: int
    cancelled_jobs: int


class QueueStatsResponse(BaseModel):
    """队列统计响应"""
    total_tasks: int
    pending_tasks: int
    running_tasks: int
    completed_tasks: int
    failed_tasks: int
    cancelled_tasks: int
    active_workers: int
    queue_size: int