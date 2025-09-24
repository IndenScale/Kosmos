import uuid
import hashlib
import base64
import os
import mimetypes
from datetime import datetime
from typing import List, Dict
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import desc
from fastapi import UploadFile, HTTPException, status
from minio import Minio
from io import BytesIO

from ..models import Document, Original, Asset, User, Job, Bookmark, OntologyChangeProposal, Chunk, DocumentAssetContext
from ..core.config import settings
from ..utils.file_utils import calculate_file_hash, detect_mime_type, generate_object_name
from ..utils.storage_utils import generate_storage_path, parse_storage_path
from ..utils.pagination_utils import decode_cursor, create_paginated_response
from ..core.object_storage import get_minio_client
from ..schemas.document import ContentSummary, AssetSummary, AssetTypeSummary, JobSummary, JobStatusSummary
from ..models.asset import AssetType
from ..models.job import Job, JobType

def get_job_summary(db: Session, document_id: uuid.UUID) -> JobSummary | None:
    """
    Calculates and returns the job summary for a given document.
    """
    jobs = db.query(Job).filter(Job.document_id == document_id).all()
    if not jobs:
        return JobSummary(total_jobs=0, by_type={})

    total_jobs = len(jobs)
    summary_by_type = {}

    for job in jobs:
        job_type = job.job_type
        job_status = job.status

        if job_type not in summary_by_type:
            summary_by_type[job_type] = JobStatusSummary()

        summary_by_type[job_type].total += 1
        summary_by_type[job_type].status_counts[job_status] = summary_by_type[job_type].status_counts.get(job_status, 0) + 1

    return JobSummary(total_jobs=total_jobs, by_type=summary_by_type)

def get_job_summaries_for_documents(db: Session, document_ids: List[uuid.UUID]) -> Dict[uuid.UUID, JobSummary]:
    """
    Calculates and returns job summaries for a list of documents in a single query.
    """
    if not document_ids:
        return {}

    document_ids_str = [str(doc_id) for doc_id in document_ids]
    jobs = db.query(Job).filter(Job.document_id.in_(document_ids)).all()
    
    summaries = {doc_id: JobSummary(total_jobs=0, by_type={}) for doc_id in document_ids}

    for job in jobs:
        doc_id = job.document_id
        if doc_id not in summaries:
            continue

        summary = summaries[doc_id]
        
        summary.total_jobs += 1
        job_type = job.job_type
        job_status = job.status

        if job_type not in summary.by_type:
            summary.by_type[job_type] = JobStatusSummary()

        summary.by_type[job_type].total += 1
        summary.by_type[job_type].status_counts[job_status] = summary.by_type[job_type].status_counts.get(job_status, 0) + 1
        
    return summaries

def get_asset_summary(db: Session, document: Document) -> AssetSummary | None:
    """
    Calculates and returns the asset summary for a given document.
    """
    asset_contexts = document.asset_contexts
    if not asset_contexts:
        return AssetSummary(total_assets=0, by_type={})

    total_assets = len(asset_contexts)
    summary_by_type = {}

    for context in asset_contexts:
        asset = context.asset
        asset_type = asset.asset_type

        if asset_type not in summary_by_type:
            summary_by_type[asset_type] = AssetTypeSummary()

        summary_by_type[asset_type].total += 1
        if context.analysis_result:
            summary_by_type[asset_type].described += 1
        else:
            summary_by_type[asset_type].not_described += 1
            
    return AssetSummary(total_assets=total_assets, by_type=summary_by_type)

def get_content_summary(db: Session, document: Document) -> ContentSummary | None:
    """
    Calculates and returns the content summary for a given document.
    """
    if not document.canonical_content:
        return None

    content = document.canonical_content
    
    # Calculate total lines from page mappings
    total_lines = 0
    if content.page_mappings:
        # Assuming line numbers are continuous and start from 1
        max_line = max(pm.line_to for pm in content.page_mappings)
        total_lines = max_line

    # Get total pages from the count of unique page numbers
    total_pages = 0
    if content.page_mappings:
        total_pages = len(set(pm.page_number for pm in content.page_mappings))

    return ContentSummary(
        total_pages=total_pages,
        total_lines=total_lines,
        total_chars=content.size
    )

def get_documents_in_knowledge_space_paginated(
    db: Session, 
    knowledge_space_id: uuid.UUID, 
    cursor: str | None, 
    page_size: int,
    status: str | None = None,
    original_filename_like: str | None = None,
    extension: str | None = None
) -> (List[Document], int):
    """
    Gets documents in a specific knowledge space with support for cursor pagination and filtering.
    This version is optimized to eager-load relationships for summary calculation.
    Returns the list of documents and the total count of matching documents.
    """
    query = db.query(Document).filter(Document.knowledge_space_id == knowledge_space_id)

    # Apply filters
    if status:
        query = query.filter(Document.status == status)
    if original_filename_like:
        query = query.filter(Document.original_filename.ilike(f"%{original_filename_like}%"))
    if extension:
        dot_extension = f".{extension}" if not extension.startswith('.') else extension
        query = query.filter(Document.original_filename.endswith(dot_extension))

    # Get the total count *before* applying pagination.
    total_count = query.count()

    # Apply cursor-based pagination
    if cursor:
        cursor_time = decode_cursor(cursor)
        if cursor_time:
            query = query.filter(Document.created_at < cursor_time)

    # Add eager loading to the final query to prevent N+1 issues
    documents = query.options(
        selectinload(Document.asset_contexts).selectinload(DocumentAssetContext.asset),
        joinedload(Document.canonical_content, innerjoin=False)
    ).order_by(desc(Document.created_at)).limit(page_size).all()

    return documents, total_count

def build_document_read_list_from_documents(db: Session, documents: List[Document]) -> List[dict]:
    """
    Constructs a list of rich document representations (including summaries)
    from a list of Document objects. Assumes relationships for content and assets
    have been eager-loaded.
    """
    if not documents:
        return []

    doc_ids = [doc.id for doc in documents]
    job_summaries = get_job_summaries_for_documents(db, doc_ids)

    response_data = []
    for doc in documents:
        content_summary = get_content_summary(db, doc)
        asset_summary = get_asset_summary(db, doc)
        job_summary = job_summaries.get(doc.id)
        
        response_data.append({
            "id": doc.id,
            "knowledge_space_id": doc.knowledge_space_id,
            "uploaded_by": doc.uploaded_by,
            "created_at": doc.created_at,
            "original_filename": doc.original_filename,
            "status": doc.status,
            "content_summary": content_summary,
            "asset_summary": asset_summary,
            "job_summary": job_summary,
        })
    return response_data

def create_or_get_original(
    db: Session,
    contents: bytes,
    filename: str,
    reported_mime_type: str,
) -> Original:
    """
    根据文件内容（哈希）查找或创建 Original 记录。
    这是幂等操作，如果内容已存在，则增加引用计数；否则，创建新记录并上传。
    """
    sha256_hash = calculate_file_hash(contents)
    original = db.query(Original).filter(Original.original_hash == sha256_hash).first()

    if original:
        original.reference_count += 1
    else:
        minio = get_minio_client()
        file_size = len(contents)
        detected_mime_type = detect_mime_type(filename)
        object_name = generate_object_name(sha256_hash, filename)
        storage_path = generate_storage_path(settings.MINIO_BUCKET_ORIGINALS, object_name)

        minio.put_object(
            bucket_name=settings.MINIO_BUCKET_ORIGINALS,
            object_name=object_name,
            data=BytesIO(contents),
            length=file_size,
            content_type=reported_mime_type
        )

        original = Original(
            original_hash=sha256_hash,
            reported_file_type=reported_mime_type,
            detected_mime_type=detected_mime_type,
            size=file_size,
            storage_path=storage_path,
            reference_count=1
        )
        db.add(original)
    
    # Flush to ensure the original.id is available if it's a new record
    db.flush()
    return original

def create_document_record(
    db: Session,
    knowledge_space_id: uuid.UUID,
    original_id: uuid.UUID,
    original_filename: str,
    uploader_id: uuid.UUID,
    parent_document_id: uuid.UUID = None
) -> Document:
    """
    在数据库中创建并返回一个新的 Document 记录。
    """
    new_document = Document(
        knowledge_space_id=knowledge_space_id,
        original_id=original_id,
        original_filename=original_filename,
        uploaded_by=uploader_id,
        parent_document_id=parent_document_id
    )
    db.add(new_document)
    db.flush()
    return new_document

async def create_document_from_upload(
    db: Session,
    minio: Minio, # Kept for compatibility, but new logic uses get_minio_client()
    knowledge_space_id: uuid.UUID,
    file: UploadFile,
    uploader: User,
    job_service = None,
    force: bool = False
) -> Document:
    """
    处理文件上传、创建 Original 和 Document 记录的核心逻辑。
    此函数现在使用重构后的辅助函数。
    """
    # 步骤 1: 检查文件名唯一性
    existing_doc = db.query(Document).filter(
        Document.knowledge_space_id == knowledge_space_id,
        Document.original_filename == file.filename
    ).first()
    if existing_doc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"文件名 '{file.filename}' 已在此知识空间中存在。"
        )

    # 步骤 2: 读取内容并创建或获取 Original
    contents = await file.read()
    original = create_or_get_original(
        db=db,
        contents=contents,
        filename=file.filename,
        reported_mime_type=file.content_type
    )

    # 步骤 3: 创建 Document 记录
    new_document = create_document_record(
        db=db,
        knowledge_space_id=knowledge_space_id,
        original_id=original.id,
        original_filename=file.filename,
        uploader_id=uploader.id
    )

    db.commit()
    db.refresh(new_document)

    # 步骤 4: 提交处理作业
    if job_service:
        try:
            job_service.submit_document_for_processing(
                document_id=new_document.id,
                initiator_id=uploader.id,
                force=force
            )
            print(f"已成功为文档 {new_document.id} 提交处理请求。")
        except Exception as e:
            print(f"为文档 {new_document.id} 提交处理作业时失败: {e}")
    else:
        print("警告: 未提供 job_service，文档将不会被自动处理。")

    return new_document

def _delete_document_no_commit(db: Session, document: Document):
    """
    删除文档的核心逻辑，但不提交事务。
    """
    if document.original:
        document.original.reference_count -= 1

    if document.asset_contexts:
        for asset_context in document.asset_contexts:
            asset_context.asset.reference_count -= 1
    
    db.delete(document)

def delete_document(db: Session, document: Document):
    """
    安全地删除单个文档记录并提交事务。
    """
    try:
        _delete_document_no_commit(db, document)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error deleting document {document.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除文档时发生内部错误。"
        )

def cleanup_knowledge_space(db: Session, knowledge_space_id: uuid.UUID):
    """
    Atomically cleans up a knowledge space, deleting all documents and their
    associated data in the correct dependency order.
    """
    try:
        # 1. Get all document IDs within the knowledge space
        document_ids_query = db.query(Document.id).filter(Document.knowledge_space_id == knowledge_space_id)
        document_ids = [item[0] for item in document_ids_query.all()]

        if not document_ids:
            # If there are no documents, still clean up KS-level items
            db.query(Job).filter(Job.knowledge_space_id == knowledge_space_id).delete(synchronize_session=False)
            db.query(Bookmark).filter(Bookmark.knowledge_space_id == knowledge_space_id).delete(synchronize_session=False)
            db.query(OntologyChangeProposal).filter(OntologyChangeProposal.knowledge_space_id == knowledge_space_id).delete(synchronize_session=False)
            db.commit()
            return

        # 2. Delete all dependent records using the collected document IDs
        db.query(Chunk).filter(Chunk.document_id.in_(document_ids)).delete(synchronize_session=False)
        db.query(Job).filter(Job.document_id.in_(document_ids)).delete(synchronize_session=False)
        db.query(Bookmark).filter(Bookmark.document_id.in_(document_ids)).delete(synchronize_session=False)
        db.query(DocumentAssetContext).filter(DocumentAssetContext.document_id.in_(document_ids)).delete(synchronize_session=False)
        
        # Also delete jobs that are only linked at the knowledge space level
        db.query(Job).filter(Job.knowledge_space_id == knowledge_space_id).delete(synchronize_session=False)

        # 3. Decrement reference counts for Originals and Assets
        documents_to_delete = db.query(Document).options(
            joinedload(Document.original),
            joinedload(Document.asset_contexts).joinedload(DocumentAssetContext.asset)
        ).filter(Document.id.in_(document_ids)).all()

        for doc in documents_to_delete:
            if doc.original:
                doc.original.reference_count -= 1
            for asset_context in doc.asset_contexts:
                if asset_context.asset:
                    asset_context.asset.reference_count -= 1

        # 4. Finally, delete the documents themselves
        db.query(Document).filter(Document.id.in_(document_ids)).delete(synchronize_session=False)
        
        # 5. Clean up any remaining KS-level items
        db.query(Bookmark).filter(Bookmark.knowledge_space_id == knowledge_space_id).delete(synchronize_session=False)
        db.query(OntologyChangeProposal).filter(OntologyChangeProposal.knowledge_space_id == knowledge_space_id).delete(synchronize_session=False)

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error cleaning up knowledge space {knowledge_space_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while cleaning up the knowledge space."
        )

def get_document_for_download(db: Session, document_id: uuid.UUID) -> tuple[Document | None, Original | None]:
    """
    获取文档及其关联的原始文件元数据，用于下载，并更新访问时间。
    """
    document = db.query(Document).options(joinedload(Document.original)).filter(Document.id == document_id).first()
    if not document or not document.original:
        return None, None

    now = datetime.utcnow()
    document.last_accessed_at = now
    document.original.last_accessed_at = now

    try:
        db.commit()
        db.refresh(document)
        db.refresh(document.original)
    except Exception as e:
        db.rollback()
        raise e

    return document, document.original

def download_original_file(minio: Minio, original: Original):
    """
    从 Minio 流式传输文件的辅助函数。
    """
    try:
        bucket_name, object_name = parse_storage_path(original.storage_path)
        response = minio.get_object(
            bucket_name=bucket_name,
            object_name=object_name
        )
        return response
    except Exception as e:
        print(f"Error fetching file from Minio: {e}")
        raise

def delete_documents_by_ids(db: Session, knowledge_space_id: uuid.UUID, document_ids: list[uuid.UUID]) -> int:
    """
    Deletes a list of documents from a specific knowledge space.
    Ensures that all documents belong to the specified knowledge space.
    """
    if not document_ids:
        return 0

    document_ids_str = [str(doc_id) for doc_id in document_ids]
    # Security check: Verify all documents belong to the specified knowledge space
    query = db.query(Document).filter(
        Document.id.in_(document_ids),
        Document.knowledge_space_id == knowledge_space_id
    )
    documents_to_delete = query.all()

    if len(documents_to_delete) != len(set(document_ids)):
        # This means some of the provided IDs do not belong to the user's KS or do not exist.
        # For security, we abort the operation.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="One or more documents are not found in this knowledge space or you do not have permission to delete them."
        )

    try:
        for doc in documents_to_delete:
            # This helper function contains the core deletion logic for a single document
            _delete_document_no_commit(db, doc)
        
        db.commit()
        return len(documents_to_delete)
    except Exception as e:
        db.rollback()
        print(f"Error during bulk deletion of documents in knowledge space {knowledge_space_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred during bulk document deletion."
        )
