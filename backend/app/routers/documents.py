import uuid
from typing import Union, List, Dict, Any, Optional, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import StreamingResponse, JSONResponse
from minio import Minio

from ..core.db import get_db
from sqlalchemy.orm import Session
from ..models.user import User
from ..models.document import Document
from ..models.asset import AssetAnalysisStatus, Asset
from ..models.membership import KnowledgeSpaceMember
from ..models.job import Job
from ..models.bookmark import Bookmark
from ..models.ontology_change_proposal import OntologyChangeProposal
from ..dependencies import get_current_user, get_member_or_404, require_role, get_document_and_verify_membership, require_super_admin, get_reading_service, get_bookmark_service, get_asset_service
from ..core.object_storage import get_minio_client
from ..services import document_service
from ..services.reading_service import ReadingService
from ..services.bookmark_service import BookmarkService
from ..schemas.document import DocumentRead
from ..schemas.reading import GrepRequest
from ..schemas.pagination import PaginatedResponse
from ..tasks import analyze_asset_actor

router = APIRouter()





# --- Schemas ---
class AssetMetadata(BaseModel):
    asset_id: uuid.UUID
    asset_type: str
    file_type: str
    analysis_status: AssetAnalysisStatus
    created_at: datetime

    class Config:
        from_attributes = True

# --- Endpoints ---

from ..services.asset_service import AssetService
from .. import schemas

# ... (other imports)

# --- Endpoints ---

@router.get(
    "/{document_id}/assets/{asset_id}/analysis",
    response_model=schemas.AssetAnalysisResponse,
    summary="获取资产在文档上下文中的分析结果"
)
def get_asset_analysis_in_document_context(
    document_id: uuid.UUID,
    asset_id: uuid.UUID,
    asset_service: AssetService = Depends(get_asset_service),
    db: Session = Depends(get_db),
    # This dependency implicitly handles permission checks for the document
    document: Document = Depends(get_document_and_verify_membership),
):
    """
    查询资产在特定文档上下文中的 VLM 分析状态和结果。
    """
    try:
        # 尝试获取已完成的分析结果
        completed_result = asset_service.get_analysis_result(
            asset_id=asset_id,
            document_id=document_id
        )

        if completed_result:
            return completed_result

        # 如果没有已完成的结果，则获取资产的当前状态
        asset = db.query(Asset).filter(Asset.id == asset_id).first()
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")

        return schemas.AssetAnalysisResponse(
            analysis_status=asset.analysis_status.value,
            description=None,
            model_version=None,
            detail=f"Analysis status is '{asset.analysis_status.value}'. Result is not yet available."
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        # Adding more context to the error log for better debugging
        print(f"Error getting asset analysis for asset {asset_id} in doc {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"获取分析结果失败: {e}")

@router.get(
    "/{document_id}/assets",
    response_model=List[AssetMetadata],
    summary="列出与文档关联的所有资产"
)
# ... (rest of the file)

def list_document_assets(
    document_id: uuid.UUID,
    reading_service: ReadingService = Depends(get_reading_service),
    document: Document = Depends(get_document_and_verify_membership), # 权限检查
):
    """
    检索与特定文档关联的所有资产的元数据列表。
    需要对文档所在知识空间的成员权限。
    """
    return reading_service.list_assets_by_document_id(document_id=document_id)


@router.get(
    "/{document_id}",
    response_model=DocumentRead,
    summary="Get document details"
)
def get_document_details(
    document: Document = Depends(get_document_and_verify_membership),
    db: Session = Depends(get_db),
):
    """
    Retrieve the details and status of a specific document.
    Requires membership to the knowledge space the document belongs to.
    """
    content_summary = document_service.get_content_summary(db, document)
    asset_summary = document_service.get_asset_summary(db, document)
    job_summary = document_service.get_job_summary(db, document.id)

    response_data = {
        "id": document.id,
        "knowledge_space_id": document.knowledge_space_id,
        "uploaded_by": document.uploaded_by,
        "created_at": document.created_at,
        "original_filename": document.original_filename,
        "status": document.status,
        "content_summary": content_summary,
        "asset_summary": asset_summary,
        "job_summary": job_summary,
    }

    return DocumentRead.model_validate(response_data)


from ..services import JobService
from ..dependencies import get_current_user, get_job_service
from ..models.credential import CredentialType

# (Assuming other imports like APIRouter, Depends, uuid, schemas, etc., are already there)

# ... (other routes) ...

from ..dependencies import get_job_service
from ..models.credential import CredentialType
from .. import schemas, models


# --- Schemas for Analysis Coordination Report ---
class AssetJobIdentifier(BaseModel):
    asset_id: uuid.UUID
    job_id: uuid.UUID

class AnalysisReportSummary(BaseModel):
    total_assets_processed: int = 0
    results_recovered_from_completed_jobs: int = 0
    orphaned_jobs_rescheduled: int = 0
    new_jobs_created: int = 0
    invalid_jobs_aborted: int = 0
    jobs_found_running: int = 0
    assets_skipped_no_action_needed: int = 0

class AnalysisReportDetails(BaseModel):
    results_recovered: List[AssetJobIdentifier] = []
    jobs_rescheduled: List[AssetJobIdentifier] = []
    jobs_created: List[AssetJobIdentifier] = []
    jobs_aborted: List[uuid.UUID] = []

class AnalysisCoordinationReport(BaseModel):
    document_id: uuid.UUID
    summary: AnalysisReportSummary
    details: AnalysisReportDetails

class CoordinateAssetAnalysisRequest(BaseModel):
    asset_ids: Optional[List[uuid.UUID]] = None
    force: bool = False


@router.post(
    "/{document_id}/analyze-assets",
    response_model=AnalysisCoordinationReport,
    status_code=status.HTTP_200_OK,
    summary="Coordinate Asset Analysis for a Document",
    description="""
    A robust, idempotent endpoint to create, fix, or re-trigger asset analysis jobs for a document.

    - **For new assets**: It creates and dispatches new analysis jobs.
    - **For completed jobs**: It recovers the results to ensure data consistency.
    - **For pending but lost jobs**: It re-schedules them.
    - **For failed/aborted jobs**: It creates new jobs to replace them.
    - **For duplicate jobs**: It cleans them up by aborting redundant ones.
    - **For running jobs**: It leaves them untouched.
    """
)
def coordinate_asset_analysis(
    document_id: uuid.UUID,
    request: CoordinateAssetAnalysisRequest,
    db: Session = Depends(get_db),
    job_service: JobService = Depends(get_job_service),
    current_user: models.User = Depends(get_current_user),
    document: models.Document = Depends(get_document_and_verify_membership),
) -> dict:
    """
    Coordinates the asset analysis process for all or a subset of assets in a document.
    """
    # HACK: Force the service to use the request's primary DB session
    # This ensures all operations are part of the same transaction
    # that FastAPI will commit at the end of the request.
    job_service.db = db

    report_data = job_service.coordinate_asset_analysis_for_document(
        document_id=document_id,
        initiator_id=current_user.id,
        target_asset_ids=request.asset_ids,
        force=request.force
    )

    # Pydantic models expect dicts, not defaultdicts
    report_data['summary'] = dict(report_data['summary'])
    report_data['details'] = dict(report_data['details'])
    report_data['document_id'] = document_id

    return report_data


@router.post(
    "/{document_id}/process",
    response_model=schemas.Job,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger Document Processing (Chunking)",
    description="A convenience endpoint to create and launch a new chunking job for a document. This is a shortcut for the main job creation endpoint."
)
def trigger_document_processing(
    document_id: uuid.UUID,
    job_service: JobService = Depends(get_job_service),
    current_user: models.User = Depends(get_current_user),
) -> models.Job:
    """
    Initiates the document chunking process by creating a job in the background.

    This endpoint performs pre-flight checks to ensure a valid credential exists
    before queueing the job.
    """
    try:
        # We use a sensible default for the credential type preference.
        # This could be exposed as a query parameter if more flexibility is needed.
        job = job_service.create_chunking_job(
            document_id=document_id,
            initiator_id=current_user.id,
            credential_type_preference=CredentialType.LLM
        )
        return job
    except HTTPException as e:
        # Re-raise HTTPException to preserve status code and detail
        raise e
    except Exception as e:
        # Catch any other unexpected errors from the service layer
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create chunking job: {e}"
        )




@router.get(
    "/{document_id}/download",
    response_class=StreamingResponse,
    summary="Download the original document file"
)
def download_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    minio: Minio = Depends(get_minio_client),
    # This dependency gets the document and verifies the user is a member
    document: Document = Depends(get_document_and_verify_membership),
):
    """
    Download the original file for a document.
    Requires membership to the knowledge space the document belongs to.
    """
    _, original = document_service.get_document_for_download(db=db, document_id=document_id)

    if not original:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Original file metadata not found")

    try:
        response = document_service.download_original_file(minio=minio, original=original)

        headers = {
            'Content-Disposition': f'attachment; filename="{document.original_filename}"',
            'Content-Type': original.reported_file_type, # Use the browser-reported type for download
            'Content-Length': str(original.size)
        }

        return StreamingResponse(response.stream(32*1024), headers=headers)

    except Exception as e:
        # Log the exception e
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not retrieve file from storage")
    finally:
        if 'response' in locals() and response:
            response.close()
            response.release_conn()



@router.delete(
    "/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clean up all documents and associated data in a knowledge space"
)
def cleanup_knowledge_space(
    knowledge_space_id: uuid.UUID = Query(..., description="The ID of the knowledge space to clean up"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Clean up a knowledge space by deleting all documents and associated data.
    This action is protected and requires the user to be an 'owner' of the knowledge space.

    This will delete all documents, jobs, bookmarks, and other related data within the specified knowledge space.
    """
    # 1. Permission check: User must be an owner.
    membership = db.query(KnowledgeSpaceMember).filter(
        KnowledgeSpaceMember.knowledge_space_id == knowledge_space_id,
        KnowledgeSpaceMember.user_id == current_user.id
    ).first()

    if not membership or membership.role not in ["owner"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to clean up this knowledge space."
        )

    # 2. Call the service to perform the cleanup
    document_service.cleanup_knowledge_space(db=db, knowledge_space_id=knowledge_space_id)

    return None


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document"
)
def delete_document_endpoint(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a document. This action is protected and requires the user to be
    an 'owner' or 'editor' of the knowledge space the document belongs to.

    This operation only deletes the document record and decrements the reference
    counts of the associated files. The actual files are removed later by a
    separate garbage collection process if their reference count drops to zero.
    """
    # First, get the document and verify the user has at least editor permissions.
    # We can reuse the dependency logic for this.
    document = get_document_and_verify_membership(
        document_id=document_id,
        db=db,
        current_user=current_user,
        # Manually check for required role within the endpoint
    )

    # Now, check if the user has the required role ('owner' or 'editor')
    membership = db.query(KnowledgeSpaceMember).filter(
        KnowledgeSpaceMember.knowledge_space_id == document.knowledge_space_id,
        KnowledgeSpaceMember.user_id == current_user.id
    ).first()

    if not membership or membership.role not in ["owner", "editor"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete documents in this knowledge space."
        )

    document_service.delete_document(db=db, document=document)
    return None
