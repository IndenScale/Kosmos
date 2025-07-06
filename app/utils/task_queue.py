import asyncio
import time
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum
import uuid
from concurrent.futures import ThreadPoolExecutor
import threading

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"

@dataclass
class Task:
    id: str
    func: Callable
    args: tuple
    kwargs: dict
    timeout: int = 300
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    created_at: float = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()

class AsyncTaskQueue:
    """异步任务队列管理器"""

    def __init__(self, max_concurrent_tasks: int = 3):
        self.max_concurrent_tasks = max_concurrent_tasks
        self.tasks: Dict[str, Task] = {}
        self.pending_queue = asyncio.Queue()
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent_tasks)
        self._running = False
        self._worker_task = None
        self._lock = threading.Lock()

    async def start(self):
        """启动队列处理器"""
        if self._running:
            return

        self._running = True
        self._worker_task = asyncio.create_task(self._worker())
        print(f"任务队列已启动，worker任务ID: {id(self._worker_task)}")

    async def stop(self):
        """停止队列处理器"""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        # 取消所有运行中的任务
        for task in self.running_tasks.values():
            task.cancel()

        # 等待所有任务完成
        if self.running_tasks:
            await asyncio.gather(*self.running_tasks.values(), return_exceptions=True)

        self.executor.shutdown(wait=True)

    async def add_task(self, func: Callable, *args, timeout: int = 30, **kwargs) -> str:
        """添加任务到队列"""
        task_id = str(uuid.uuid4())
        task = Task(
            id=task_id,
            func=func,
            args=args,
            kwargs=kwargs,
            timeout=timeout
        )

        with self._lock:
            self.tasks[task_id] = task

        await self.pending_queue.put(task_id)
        print(f"任务已添加到队列: {task_id}, 队列大小: {self.pending_queue.qsize()}, 运行中: {len(self.running_tasks)}")
        return task_id

    def get_task_status(self, task_id: str) -> Optional[Task]:
        """获取任务状态"""
        with self._lock:
            return self.tasks.get(task_id)

    def get_queue_stats(self) -> Dict[str, int]:
        """获取队列统计信息"""
        with self._lock:
            stats = {
                "pending": self.pending_queue.qsize(),
                "running": len(self.running_tasks),
                "total_tasks": len(self.tasks)
            }

            status_counts = {}
            for task in self.tasks.values():
                status = task.status.value
                status_counts[status] = status_counts.get(status, 0) + 1

            stats.update(status_counts)
            return stats

    async def _worker(self):
        """队列工作器"""
        print("任务队列worker开始运行")
        while self._running:
            try:
                # 检查是否可以处理新任务
                if len(self.running_tasks) >= self.max_concurrent_tasks:
                    print(f"达到最大并发任务数 {self.max_concurrent_tasks}，等待...")
                    await asyncio.sleep(0.1)
                    continue

                # 获取待处理任务
                try:
                    task_id = await asyncio.wait_for(self.pending_queue.get(), timeout=1.0)
                    print(f"从队列获取任务: {task_id}")
                except asyncio.TimeoutError:
                    # 每秒检查一次队列状态
                    continue

                with self._lock:
                    task = self.tasks.get(task_id)

                if not task or task.status != TaskStatus.PENDING:
                    print(f"任务不存在或状态异常: {task_id}")
                    continue

                print(f"开始执行任务: {task_id}")
                # 启动任务
                asyncio_task = asyncio.create_task(self._execute_task(task))
                self.running_tasks[task_id] = asyncio_task

            except Exception as e:
                print(f"队列工作器错误: {e}")
                await asyncio.sleep(1)
        
        print("任务队列worker停止运行")

    async def _execute_task(self, task: Task):
        """执行单个任务"""
        task_id = task.id

        try:
            # 更新任务状态
            with self._lock:
                task.status = TaskStatus.RUNNING
                task.started_at = time.time()

            # 在线程池中执行任务（带超时）
            loop = asyncio.get_event_loop()

            try:
                result = await asyncio.wait_for(
                    loop.run_in_executor(
                        self.executor,
                        lambda: task.func(*task.args, **task.kwargs)
                    ),
                    timeout=task.timeout
                )

                # 任务成功完成
                with self._lock:
                    task.status = TaskStatus.COMPLETED
                    task.result = result
                    task.completed_at = time.time()

            except asyncio.TimeoutError:
                # 任务超时
                with self._lock:
                    task.status = TaskStatus.TIMEOUT
                    task.error = f"任务超时（{task.timeout}秒）"
                    task.completed_at = time.time()

            except Exception as e:
                # 任务执行失败
                with self._lock:
                    task.status = TaskStatus.FAILED
                    task.error = str(e)
                    task.completed_at = time.time()

        finally:
            # 清理运行中的任务记录
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]

# 全局任务队列实例
task_queue = AsyncTaskQueue(max_concurrent_tasks=3)