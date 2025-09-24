
import uuid
import time
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..models import User
from ..models.job import JobType, JobStatus
from ..dependencies import get_current_user, get_job_service, get_document_and_verify_membership
from ..schemas.job import (
    Job, JobCreate, JobBatchCreateRequest, JobFilterParams, 
    BatchJobCreationResponse, JobAbortRequest, JobAbortResponse, JobBulkDeleteRequest
)
from ..schemas.pagination import PaginatedJobResponse
from ..services import JobService

router = APIRouter(
    prefix="/jobs",
    tags=["Jobs"],
)

# Pydantic models for the /types endpoint
class ContextFieldSchema(BaseModel):
    type: str
    description: str
    default: Optional[Any] = None
    enum: Optional[List[str]] = None

class JobTypeInfo(BaseModel):
    description: str
    context_schema: Dict[str, ContextFieldSchema] = Field(default_factory=dict)


@router.get(
    "/types",
    response_model=Dict[str, JobTypeInfo],
    summary="Get supported job types and their context schemas",
    description="Provides a list of all creatable job types, their descriptions, and the expected schema for the 'context' field.",
)
def get_job_types_info():
    """
    Returns a detailed schema for job types that can be created via the API.
    This helps clients understand what parameters are available and required for each job type.
    """
    from ..models.credential import CredentialType

    creatable_job_types = {
        JobType.CONTENT_EXTRACTION: JobTypeInfo(
            description="Extracts canonical content and assets from a document using tools like LibreOffice and MinerU.",
            context_schema={
                "content_extraction_strategy": ContextFieldSchema(
                    type="string",
                    description="Strategy for content extraction (e.g., reuse existing).",
                    enum=["reuse_any", "force_reextraction"]
                ),
                "asset_analysis_strategy": ContextFieldSchema(
                    type="string",
                    description="Strategy for asset analysis during extraction.",
                    enum=["reuse_any", "reuse_within_document", "force_reanalysis"]
                ),
                "chunking_strategy_name": ContextFieldSchema(
                    type="string",
                    description="Name of the subsequent chunking strategy to use."
                )
            }
        ),
        JobType.DOCUMENT_PROCESSING: JobTypeInfo(
            description="Orchestrates the end-to-end processing of a document, including decomposition of embedded files.",
            context_schema={
                "extract_embedded_documents": ContextFieldSchema(
                    type="boolean",
                    description="Whether to extract and process embedded documents within a container file (e.g., a .docx).",
                    default=True,
                )
            }
        ),
        JobType.CHUNKING: JobTypeInfo(
            description="Splits a document into smaller pieces (chunks) for further processing.",
            context_schema={
                "credential_type_preference": ContextFieldSchema(
                    type="string",
                    description="Optional. Preferred credential type for the chunking model.",
                    enum=[e.value for e in CredentialType if e != CredentialType.NONE]
                )
            }
        ),
        JobType.INDEXING: JobTypeInfo(
            description="Creates vector embeddings for document chunks and stores them in the vector database.",
            context_schema={}
        ),
        JobType.TAGGING: JobTypeInfo(
            description="Analyzes document content to automatically assign tags or labels.",
            context_schema={
                "mode": ContextFieldSchema(
                    type="string",
                    description="The tagging mode.",
                    default="assignment"
                )
            }
        ),
        JobType.ASSET_ANALYSIS: JobTypeInfo(
            description="Analyzes visual assets (e.g., images) within a document. This will create one job per asset.",
            context_schema={}
        ),
    }
    
    return {job_type.value: info for job_type, info in creatable_job_types.items()}


def _poll_for_job_status(job_ids: List[uuid.UUID], job_service: JobService, timeout: float = 2.0, interval: float = 0.3) -> List[Job]:
    """
    Polls for the status of created jobs for a short period.
    Returns the most up-to-date job objects.
    """
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        updated_jobs = [job_service.get_job_by_id(job_id) for job_id in job_ids]
        if any(job.status != JobStatus.PENDING for job in updated_jobs if job):
            return [job for job in updated_jobs if job]
            
        time.sleep(interval)
        
    final_jobs = [job_service.get_job_by_id(job_id) for job_id in job_ids]
    return [job for job in final_jobs if job]

@router.post(
    "/",
    response_model=List[Job],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a new Job or set of Jobs",
    description="Create one or more jobs for a document. Certain job types like 'asset_analysis' may generate multiple jobs.",
)
def create_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    job_service: JobService = Depends(get_job_service),
):
    document = get_document_and_verify_membership(
        document_id=payload.document_id, db=db, current_user=current_user
    )

    job_creators = {
        JobType.CHUNKING: lambda: job_service.create_chunking_job(
            document_id=document.id,
            initiator_id=current_user.id,
            credential_type_preference=payload.context.get("credential_type_preference") if payload.context else None,
            force=payload.force,
        ),
        JobType.INDEXING: lambda: job_service.create_indexing_job(
            document_id=document.id,
            initiator_id=current_user.id,
            force=payload.force,
        ),
        JobType.TAGGING: lambda: job_service.create_tagging_job(
            document_id=document.id,
            initiator_id=current_user.id,
            mode=payload.context.get("mode", "assignment") if payload.context else "assignment",
            force=payload.force,
        ),
        JobType.DOCUMENT_PROCESSING: lambda: job_service.submit_document_for_processing(
            document_id=document.id,
            initiator_id=current_user.id,
            force=payload.force,
            context=payload.context,
        ),
        JobType.ASSET_ANALYSIS: lambda: job_service.create_asset_analysis_jobs_for_document(
            document_id=document.id,
            initiator_id=current_user.id,
            force=payload.force,
        ),
        JobType.CONTENT_EXTRACTION: lambda: [job_service.create_content_extraction_job(
            document_id=document.id,
            initiator_id=current_user.id,
            force=payload.force,
            context=payload.context,
        )],
    }

    creator = job_creators.get(payload.job_type)
    if not creator:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job type '{payload.job_type}' is not supported for direct creation.",
        )

    try:
        jobs = creator()
        # The service layer is now responsible for committing and dispatching.
        # We just need to poll for the status of the returned jobs.
        if not jobs:
            return []
            
        job_ids = [job.id for job in jobs]
        updated_jobs = _poll_for_job_status(job_ids, job_service)
        return updated_jobs
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create job(s): {e}",
        )

@router.post(
    "/batch",
    response_model=BatchJobCreationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create jobs for a batch of documents",
)
def create_batch_jobs(
    payload: JobBatchCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    job_service: JobService = Depends(get_job_service),
):
    submitted_jobs: List[Job] = []
    failed_documents: Dict[uuid.UUID, str] = {}
    all_created_job_ids: List[uuid.UUID] = []

    for doc_id in payload.document_ids:
        try:
            job_payload = JobCreate(
                document_id=doc_id,
                job_type=payload.job_type,
                force=payload.force,
                context=payload.context,
            )
            created_jobs = create_job(
                payload=job_payload,
                db=db,
                current_user=current_user,
                job_service=job_service,
            )
            all_created_job_ids.extend([job.id for job in created_jobs])
        except HTTPException as e:
            failed_documents[doc_id] = e.detail
        except Exception as e:
            failed_documents[doc_id] = str(e)

    if all_created_job_ids:
        submitted_jobs = _poll_for_job_status(all_created_job_ids, job_service)

    return BatchJobCreationResponse(
        submitted_jobs=submitted_jobs,
        failed_documents=failed_documents,
    )

@router.post(
    "/abort-by-documents",
    response_model=JobAbortResponse,
    summary="Abort pending or running jobs for specific documents",
)
def abort_jobs(
    payload: JobAbortRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    job_service: JobService = Depends(get_job_service),
):
    aborted_count = job_service.abort_jobs_for_documents(
        document_ids=payload.document_ids,
        initiator_id=current_user.id,
        job_type=payload.job_type
    )
    
    return JobAbortResponse(aborted_jobs_count=aborted_count)

@router.get(
    "/",
    response_model=PaginatedJobResponse[Job],
    summary="List jobs with filters",
    description="Get a list of jobs, with support for filtering and cursor-based pagination.",
)
def get_jobs(
    response: Response,
    filters: JobFilterParams = Depends(JobFilterParams),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    job_service: JobService = Depends(get_job_service),
):
    # 使用job service进行权限验证
    verified_ks_id = job_service.verify_user_access_for_job_listing(
        user=current_user,
        knowledge_space_id=filters.knowledge_space_id,
        document_id=filters.document_id
    )

    jobs, total_count = job_service.get_jobs(
        user_id=current_user.id,
        knowledge_space_id=filters.knowledge_space_id,
        document_id=filters.document_id,
        job_type=filters.job_type,
        status=filters.status,
        cursor=filters.cursor,
        limit=filters.limit,
    )

    next_cursor = None
    if len(jobs) == filters.limit:
        next_cursor = jobs[-1].created_at.isoformat()

    job_id_list = [str(job.id) for job in jobs]

    return PaginatedJobResponse(
        items=jobs, 
        total_count=total_count, 
        next_cursor=next_cursor,
        job_id_list=job_id_list
    )

@router.delete(
    "/",
    status_code=status.HTTP_200_OK,
    summary="Bulk delete jobs by their IDs"
)
def delete_jobs(
    payload: JobBulkDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    job_service: JobService = Depends(get_job_service),
):
    """
    Deletes a list of jobs by their IDs.
    A user can only delete jobs that they have initiated.
    """
    deleted_count = job_service.delete_jobs_by_ids(
        job_ids=payload.job_ids,
        initiator_id=current_user.id,
        force=payload.force
    )
    return {"detail": f"Successfully deleted {deleted_count} job(s)."}

@router.get(
    "/{job_id}",
    response_model=Job,
    summary="Get job details by ID",
    description="Retrieve the full details of a specific job by its UUID.",
)
def get_job_by_id(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    job_service: JobService = Depends(get_job_service),
):
    job = job_service.get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    # 使用job service进行权限验证
    job_service.verify_user_access_to_job(user=current_user, job=job)
    
    return job
