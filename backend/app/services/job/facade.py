"""Job服务的主要Facade接口，整合所有job相关的业务逻辑。"""
import uuid
import json
import logging
from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, update, String, func
from fastapi import HTTPException

from ...models import Job, Document, DocumentAssetContext, Chunk, User
from ...models.job import JobType, JobStatus
from ...models.credential import CredentialType

# Import the refactored logic from the same package
from . import creation
from . import state_management
from . import authorization
from .utils import dispatch_job_actor
from ...utils.storage_utils import parse_storage_path

logger = logging.getLogger(__name__)

from enum import Enum

class JobCreationAction(Enum):
    SKIP = "SKIP"
    CREATE_NEW = "CREATE_NEW"
    DELETE_AND_RECREATE = "DELETE_AND_RECREATE"

class JobService:
    """Job服务的主要Facade类，提供所有job相关的业务逻辑。"""

    def __init__(self, db: Session, redis_client, minio_client):
        self.db = db
        self.redis_client = redis_client
        self.minio_client = minio_client

    # ==================== 权限验证方法 ====================

    def verify_user_access_to_job(self, user: User, job: Job) -> None:
        """验证用户对job的访问权限。"""
        authorization.verify_job_access(self.db, user, job.knowledge_space_id)

    def verify_user_access_for_job_listing(
        self,
        user: User,
        knowledge_space_id: Optional[uuid.UUID] = None,
        document_id: Optional[uuid.UUID] = None
    ) -> Optional[uuid.UUID]:
        """验证用户对job列表的访问权限。"""
        return authorization.verify_job_list_access(
            self.db, user, knowledge_space_id, document_id
        )

    # ==================== Job创建方法 ====================

    def submit_document_for_processing(self, document_id: uuid.UUID, initiator_id: uuid.UUID, force: bool = False, context: Optional[dict] = None) -> List[Job]:
        """提交文档进行处理，处理容器分解。"""
        from .orchestration import document_processing

        try:
            jobs_to_dispatch = document_processing.submit_document_for_processing(
                db=self.db,
                document_id=document_id,
                initiator_id=initiator_id,
                force=force,
                context=context
            )
            self.db.commit()
            for job in jobs_to_dispatch:
                dispatch_job_actor(job)
            return jobs_to_dispatch
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error during document submission orchestration for doc {document_id}: {e}")
            raise

    def create_chunking_job(self, document_id: uuid.UUID, initiator_id: uuid.UUID, credential_type_preference: CredentialType, force: bool = False, context: Optional[dict] = None) -> List[Job]:
        """创建分块job，如果chunks已存在且未强制则跳过。"""
        has_existing_chunks = self.db.query(Chunk).filter(Chunk.document_id == document_id).first()
        if not force and has_existing_chunks:
            logger.info(f"Skipping chunking job for document {document_id} as chunks already exist and force=False.")
            return []

        job = creation.create_chunking_job(
            db=self.db, document_id=document_id, initiator_id=initiator_id,
            credential_type_preference=credential_type_preference, force=force, context=context
        )
        self.db.commit()
        dispatch_job_actor(job)
        return [job]

    def create_indexing_job(self, document_id: uuid.UUID, initiator_id: uuid.UUID, force: bool = False) -> List[Job]:
        """创建索引job。"""
        from backend.app.services.vector_db_service import VectorDBService

        if not force:
            doc = self.db.query(Document).filter(Document.id == document_id).first()
            if not doc:
                logger.warning(f"Attempted to create indexing job for non-existent document {document_id}")
                return []

            all_chunk_ids_query = self.db.query(Chunk.id).filter(Chunk.document_id == document_id).all()
            all_chunk_ids = {str(row[0]) for row in all_chunk_ids_query}
            if not all_chunk_ids:
                logger.info(f"Skipping indexing job for document {document_id} as it has no chunks.")
                return []

            try:
                vector_db_service = VectorDBService()
                indexed_chunk_ids = set(vector_db_service.fetch_by_chunk_ids(
                    knowledge_space_id=str(doc.knowledge_space_id), chunk_ids=list(all_chunk_ids)
                ))
            except Exception as e:
                logger.error(f"Failed to connect to VectorDB: {e}. Proceeding with job creation.")
                indexed_chunk_ids = set()

            chunks_to_index = all_chunk_ids - indexed_chunk_ids
            if not chunks_to_index:
                logger.info(f"Skipping indexing job for document {document_id} as all chunks are indexed.")
                chunk_ids_as_uuids = [uuid.UUID(cid) for cid in all_chunk_ids]
                self.db.query(Chunk).filter(Chunk.id.in_(chunk_ids_as_uuids)).update({"indexing_status": "indexed"}, synchronize_session=False)
                self.db.commit()
                return []

        job = creation.create_indexing_job(
            db=self.db, document_id=document_id, initiator_id=initiator_id, force=force
        )
        self.db.commit()
        dispatch_job_actor(job)
        return [job]

    def create_tagging_job(self, document_id: uuid.UUID, initiator_id: uuid.UUID, mode: str, force: bool = False) -> List[Job]:
        """创建标签job。"""
        job = creation.create_tagging_job(
            db=self.db, document_id=document_id, initiator_id=initiator_id, mode=mode, force=force
        )
        self.db.commit()
        dispatch_job_actor(job)
        return [job]

    def create_content_extraction_job(self, document_id: uuid.UUID, initiator_id: uuid.UUID, force: bool = False, context: Optional[dict] = None) -> Job:
        """创建内容提取job。"""
        job = creation.create_content_extraction_job(
            db=self.db, document_id=document_id, initiator_id=initiator_id, force=force, context=context
        )
        self.db.commit()
        dispatch_job_actor(job)
        return job

    def create_asset_analysis_jobs_for_document(self, document_id: uuid.UUID, initiator_id: uuid.UUID, force: bool = False) -> List[Job]:
        """为文档中的所有资产创建分析job。"""
        asset_contexts = self.db.query(DocumentAssetContext).filter(
            DocumentAssetContext.document_id == document_id
        ).all()

        if not asset_contexts:
            return []

        jobs_to_create = []
        for context in asset_contexts:
            action, old_job_to_delete = self._get_analysis_job_action(context, force)

            if action == JobCreationAction.SKIP:
                continue

            if action == JobCreationAction.DELETE_AND_RECREATE:
                if old_job_to_delete:
                    logger.info(f"Deleting old invalid job {old_job_to_delete.id} before recreating.")
                    self.db.delete(old_job_to_delete)
                    self.db.flush()

            job = creation.create_asset_analysis_job(
                db=self.db,
                document_id=document_id,
                asset_id=context.asset_id,
                initiator_id=initiator_id
            )
            jobs_to_create.append(job)

        if jobs_to_create:
            self.db.commit()
            for job in jobs_to_create:
                dispatch_job_actor(job)

        return jobs_to_create

    def _get_analysis_job_action(self, context: DocumentAssetContext, force: bool) -> (JobCreationAction, Optional[Job]):
        """确定文档资产上下文的分析job应采取的操作。"""
        if force:
            if context.analysis_job_id:
                old_job = self.db.query(Job).filter(Job.id == context.analysis_job_id).first()
                return JobCreationAction.DELETE_AND_RECREATE, old_job
            return JobCreationAction.CREATE_NEW, None

        if context.analysis_result:
            logger.info(f"Skipping asset {context.asset_id}: description already exists.")
            return JobCreationAction.SKIP, None

        if not context.analysis_job_id:
            return JobCreationAction.CREATE_NEW, None

        job = self.db.query(Job).filter(Job.id == context.analysis_job_id).first()
        if not job:
            return JobCreationAction.CREATE_NEW, None

        active_or_completed_statuses = [JobStatus.PENDING, JobStatus.RUNNING, JobStatus.COMPLETED]
        if job.status in active_or_completed_statuses:
            logger.info(f"Skipping asset {context.asset_id}: found existing job {job.id} with status '{job.status.value}'.")
            return JobCreationAction.SKIP, None

        return JobCreationAction.DELETE_AND_RECREATE, job

    def create_knowledge_space_batch_job(self, knowledge_space_id: uuid.UUID, initiator_id: uuid.UUID, tasks: list[str]) -> Job:
        """创建知识空间批处理job。"""
        job = creation.create_knowledge_space_batch_job(
            db=self.db, knowledge_space_id=knowledge_space_id, initiator_id=initiator_id, tasks=tasks
        )
        self.db.commit()
        return job

    # ==================== Job状态管理方法 ====================

    def start_job(self, job_id: uuid.UUID, message: str = "Job started") -> Job:
        """将job标记为RUNNING。"""
        job = state_management.start_job(self.db, job_id)
        self.update_progress(job, "start", message)
        return job

    def update_progress(self, job: Job, step: str, message: str, **extra):
        """更新job进度并发布到Redis。"""
        state_management.update_job_progress(job, step, message, **extra)
        if self.redis_client:
            channel = f"job:{job.id}"
            payload = json.dumps({
                "job_id": str(job.id), "status": job.status.value,
                "progress": job.progress, "updated_at": datetime.utcnow().isoformat()
            })
            self.redis_client.publish(channel, payload)

    def finalize_job(self, job_id: uuid.UUID, status: JobStatus, result: dict = None, error_message: str = None):
        """
        完成job的状态。
        注意：此方法不提交事务，调用方负责提交。
        """
        if status == JobStatus.COMPLETED:
            job = state_management.complete_job(self.db, job_id, result)
            self.update_progress(job, "finished", "Job completed successfully")
        elif status == JobStatus.FAILED:
            job = state_management.fail_job(self.db, job_id, error_message)
            self.update_progress(job, "error", error_message)
        else:
            raise ValueError("finalize_job only accepts COMPLETED or FAILED status.")

    # ==================== Job查询和管理方法 ====================

    def get_job_by_id(self, job_id: uuid.UUID) -> Job | None:
        """通过ID获取job。"""
        return state_management.get_job_by_id(self.db, job_id)

    def get_jobs_by_document_id(self, document_id: uuid.UUID) -> list[Job]:
        """获取指定文档的所有job。"""
        return self.db.query(Job).filter(
            Job.document_id == document_id
        ).order_by(desc(Job.created_at)).all()

    def get_jobs(
        self,
        user_id: uuid.UUID,
        knowledge_space_id: Optional[uuid.UUID] = None,
        document_id: Optional[uuid.UUID] = None,
        job_type: Optional[JobType] = None,
        status: Optional[JobStatus] = None,
        cursor: Optional[str] = None,
        limit: int = 20,
    ) -> (List[Job], int):
        """获取job列表，支持过滤和分页。"""
        from backend.app.models import KnowledgeSpaceMember

        user_id_str = str(user_id)

        query = self.db.query(Job).join(
            KnowledgeSpaceMember, Job.knowledge_space_id == KnowledgeSpaceMember.knowledge_space_id
        ).filter(KnowledgeSpaceMember.user_id == user_id)

        if knowledge_space_id:
            query = query.filter(Job.knowledge_space_id == knowledge_space_id)
        if document_id:
            query = query.filter(Job.document_id == document_id)
        if job_type:
            query = query.filter(Job.job_type == job_type)
        if status:
            query = query.filter(Job.status == status)

        total_count = query.count()

        if cursor:
            query = query.filter(Job.created_at > datetime.fromisoformat(cursor))

        query = query.order_by(asc(Job.created_at)).limit(limit)
        return query.all(), total_count

    # ==================== Job操作方法 ====================

    def abort_jobs_for_documents(self, document_ids: List[uuid.UUID], initiator_id: uuid.UUID, job_type: Optional[JobType] = None) -> int:
        """中止指定文档的pending或running job。"""
        if not document_ids:
            return 0
        try:
            conditions = [
                Job.document_id.in_(document_ids),
                Job.status.in_([JobStatus.PENDING, JobStatus.RUNNING])
            ]
            if job_type:
                conditions.append(Job.job_type == job_type)

            stmt = update(Job).where(*conditions).values(
                status=JobStatus.ABORTED,
                error_message=f"Job aborted by user {initiator_id}"
            )
            result = self.db.execute(stmt)
            self.db.commit()
            return result.rowcount
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to abort jobs for documents {document_ids}: {e}", exc_info=True)
            raise

    def delete_jobs_by_ids(self, job_ids: List[uuid.UUID], initiator_id: uuid.UUID, force: bool = False) -> int:
        """通过ID删除job，确保用户是发起者。"""
        if not job_ids:
            return 0
        try:
            query = self.db.query(Job).filter(
                Job.id.in_(job_ids),
                Job.initiator_id == initiator_id
            )

            jobs_to_delete = query.all()
            if len(jobs_to_delete) != len(set(job_ids)):
                raise HTTPException(status_code=403, detail="One or more jobs not found or you are not the initiator.")

            if force:
                deletable_job_ids = [job.id for job in jobs_to_delete]
            else:
                final_state_jobs = [
                    job for job in jobs_to_delete
                    if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.ABORTED]
                ]
                deletable_job_ids = [job.id for job in final_state_jobs]

            if not deletable_job_ids:
                return 0

            stmt = Job.__table__.delete().where(Job.id.in_(deletable_job_ids))
            result = self.db.execute(stmt)
            self.db.commit()
            return result.rowcount
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to delete jobs {job_ids}: {e}", exc_info=True)
            raise

    def check_job_exists(self, job_id: str) -> bool:
        """检查指定ID的job是否存在。"""
        try:
            job_uuid = uuid.UUID(job_id)
            return self.db.query(Job.id).filter(Job.id == job_uuid).first() is not None
        except ValueError:
            return False

    # ==================== 复杂业务逻辑方法 ====================

    def coordinate_asset_analysis_for_document(
        self,
        document_id: uuid.UUID,
        initiator_id: uuid.UUID,
        target_asset_ids: Optional[List[uuid.UUID]] = None,
        force: bool = False
    ) -> dict:
        """协调并确保文档的资产分析。"""
        import re
        from collections import defaultdict
        from backend.app.models import CanonicalContent, Asset


        report = {
            "summary": defaultdict(int),
            "details": defaultdict(list)
        }

        try:
            # 获取权威来源：规范内容markdown
            doc = self.db.query(Document).filter(Document.id == document_id).first()
            if not doc or not doc.canonical_content_id:
                raise HTTPException(status_code=404, detail="Document or its canonical content not found.")

            cc = self.db.query(CanonicalContent).filter(CanonicalContent.id == doc.canonical_content_id).first()
            if not cc or not cc.storage_path:
                raise HTTPException(status_code=404, detail="Canonical content record or its storage path is missing.")

            try:
                bucket, object_name = parse_storage_path(cc.storage_path)
                response = self.minio_client.get_object(bucket, object_name)
                md_content = response.read().decode('utf-8')
            finally:
                response.close()
                response.release_conn()

            # 解析markdown中的所有资产ID
            authoritative_asset_ids_str = set(re.findall(r'asset://([0-9a-fA-F-]+)', md_content))
            authoritative_asset_ids = {uuid.UUID(id_str) for id_str in authoritative_asset_ids_str}

            # 如果用户提供了目标，则过滤
            if target_asset_ids:
                authoritative_asset_ids = authoritative_asset_ids.intersection(set(target_asset_ids))

            report['summary']['total_assets_processed'] = len(authoritative_asset_ids)
            if not authoritative_asset_ids:
                self.db.commit()
                return report

            # 获取所有现有上下文
            existing_contexts_list = self.db.query(DocumentAssetContext).filter(
                DocumentAssetContext.document_id == document_id,
                DocumentAssetContext.asset_id.in_(authoritative_asset_ids)
            ).all()
            contexts = {ctx.asset_id: ctx for ctx in existing_contexts_list}

            # 处理每个权威资产
            for asset_id in authoritative_asset_ids:
                context = contexts.get(asset_id)

                # 自愈：如果上下文缺失，创建它
                if not context:
                    if not self.db.query(Asset.id).filter(Asset.id == asset_id).first():
                        logger.warning(f"[SELF-HEALING-SKIP] Asset {asset_id} from markdown not found in Asset table for doc {document_id}. Skipping context creation.")
                        report['summary']['assets_skipped_not_found'] += 1
                        continue

                    context = DocumentAssetContext(
                        document_id=document_id,
                        asset_id=asset_id
                    )
                    self.db.add(context)
                    self.db.flush()
                    report['summary']['contexts_created'] += 1
                    report['details']['contexts_created'].append(str(asset_id))

                # 确定操作
                action, old_job_to_delete = self._get_analysis_job_action(context, force)

                if action == JobCreationAction.SKIP:
                    report['summary']['assets_skipped'] += 1
                    continue

                if action == JobCreationAction.DELETE_AND_RECREATE:
                    if old_job_to_delete:
                        logger.info(f"[COORDINATE] Deleting old job {old_job_to_delete.id} for asset {asset_id}.")
                        self.db.delete(old_job_to_delete)
                        self.db.flush()
                        report['summary']['old_jobs_deleted'] += 1

                # 创建新job
                job = creation.create_asset_analysis_job(
                    db=self.db,
                    document_id=document_id,
                    asset_id=asset_id,
                    initiator_id=initiator_id
                )
                dispatch_job_actor(job)
                report['summary']['jobs_created'] += 1
                report['details']['jobs_created'].append(str(job.id))

            self.db.commit()
            return report

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to coordinate asset analysis for document {document_id}: {e}", exc_info=True)
            raise