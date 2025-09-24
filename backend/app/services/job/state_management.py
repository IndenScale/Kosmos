"""
此模块包含用于管理 Job 生命周期的核心业务逻辑。
这些函数被设计为可独立测试，并由 JobService 作为 Facade 调用。
"""
import uuid
from sqlalchemy.orm import Session, joinedload

from backend.app.models import Job, Document
from backend.app.models.job import JobStatus
from .exceptions import JobNotFoundError

def get_job_by_id(db: Session, job_id: uuid.UUID) -> Job | None:
    """
    通过 ID 检索 Job，并预加载文档及其子文档关系。
    这是状态管理操作的通用前置步骤。
    """
    return db.query(Job).options(
        joinedload(Job.document).joinedload(Document.original),
        joinedload(Job.document).joinedload(Document.children)
    ).filter(Job.id == job_id).first()

def start_job(db: Session, job_id: uuid.UUID, message: str = "Job started") -> Job:
    """
    将一个 Job 标记为 RUNNING。此操作是幂等的。
    """
    from sqlalchemy import update

    # First, check if the job exists using the correct query.
    job_to_start = get_job_by_id(db, job_id)
    if not job_to_start:
        raise JobNotFoundError(f"Job {job_id} not found.")

    if job_to_start.status == JobStatus.RUNNING:
        return job_to_start

    # [FINAL FIX] Use an explicit, robust UPDATE statement.
    # This ensures the WHERE clause is correct for SQLite.
    db.execute(
        update(Job)
        .where(Job.id == job_id)
        .values(status=JobStatus.RUNNING)
    )

    # After executing the update, the original 'job_to_start' object is stale.
    # We must re-fetch it from the database to get the updated version.
    db.expire(job_to_start)
    db.refresh(job_to_start)
    return job_to_start

def update_job_progress(job: Job, step: str, message: str, **extra) -> Job:
    """
    更新 Job 的 progress 字段。
    注意：Redis 发布逻辑将在 JobService Facade 中处理。
    """
    progress_data = {"step": step, "message": message, **extra}
    job.progress = progress_data
    return job

def complete_job(db: Session, job_id: uuid.UUID, result: dict = None) -> Job:
    """
    将一个 Job 标记为 COMPLETED。
    注意：触发下游任务（如子文档处理）的编排逻辑已被移除，将由 orchestration 模块处理。
    """
    from sqlalchemy import update

    job_to_complete = get_job_by_id(db, job_id)
    if not job_to_complete:
        raise JobNotFoundError(f"Job {job_id} not found.")

    update_values = {"status": JobStatus.COMPLETED}
    if result is not None:
        update_values["result"] = result

    db.execute(
        update(Job)
        .where(Job.id == job_id)
        .values(**update_values)
    )

    db.expire(job_to_complete)
    db.refresh(job_to_complete)
    return job_to_complete

def fail_job(db: Session, job_id: uuid.UUID, error_message: str) -> Job:
    """
    将一个 Job 标记为 FAILED。
    """
    job = get_job_by_id(db, job_id)
    if not job:
        # 尝试在独立的会话中查找并更新，以提高失败处理的健壮性
        from backend.app.core.db import SessionLocal
        with SessionLocal() as new_db:
            # Use a simple query here, no need for joinedload in the fallback
            job_in_new_session = new_db.query(Job).filter(Job.id == job_id).first()
            if job_in_new_session:
                job_in_new_session.status = JobStatus.FAILED
                job_in_new_session.error_message = error_message
                new_db.commit()
                # After committing in the new session, re-fetch the job in the original session
                # to return an attached instance.
                db.expire_all() # Expire the current session to ensure we get fresh data
                return get_job_by_id(db, job_id)
        raise JobNotFoundError(f"Job {job_id} not found, even in a new session.")

    job.status = JobStatus.FAILED
    job.error_message = error_message
    return job