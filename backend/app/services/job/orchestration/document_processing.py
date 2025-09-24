"""
此模块负责编排复杂的文档处理工作流。
核心职责是处理容器文档的分解，并原子性地为父文档和所有子文档创建处理作业。
"""
import os
import uuid
import hashlib
from io import BytesIO
from sqlalchemy.orm import Session
from typing import List, Optional, Set

from backend.app.models import Document, Job, DocumentStatus
from backend.app.core.config import settings
from backend.app.core.object_storage import get_minio_client
from backend.app.services.jobs.utils import decompose_docx_and_replace_ole
from backend.app.services.jobs.creation import create_document_processing_job
# Assuming these helpers are moved to a dedicated service or are available for import
from backend.app.services.document_service import create_or_get_original, create_document_record
from backend.app.utils.file_utils import unwrap_ole_and_correct_info
from backend.app.utils.storage_utils import parse_storage_path

# --- 专业化处理配置 ---

def get_mime_whitelist() -> Optional[Set[str]]:
    """从环境变量加载 MIME 白名单。"""
    whitelist_str = os.getenv("KOSMOS_EMBEDDED_MIME_WHITELIST")
    if whitelist_str:
        return {item.strip().lower() for item in whitelist_str.split(',')}
    return None

def should_skip_legacy_office() -> bool:
    """检查是否应跳过旧版二进制 Office 文件。"""
    return os.getenv("KOSMOS_SKIP_LEGACY_OFFICE_EMBEDS", "false").lower() in ["true", "1", "yes"]

LEGACY_OFFICE_MIMES = {
    "application/msword",
    "application/vnd.ms-excel",
    "application/vnd.ms-powerpoint",
}

from backend.app.services.job.facade import JobService

# --- 专业化处理配置 ---

def get_mime_whitelist() -> Optional[Set[str]]:
    """从环境变量加载 MIME 白名单。"""
    whitelist_str = os.getenv("KOSMOS_EMBEDDED_MIME_WHITELIST")
    if whitelist_str:
        return {item.strip().lower() for item in whitelist_str.split(',')}
    return None

def should_skip_legacy_office() -> bool:
    """检查是否应跳过旧版二进制 Office 文件。"""
    return os.getenv("KOSMOS_SKIP_LEGACY_OFFICE_EMBEDS", "false").lower() in ["true", "1", "yes"]

LEGACY_OFFICE_MIMES = {
    "application/msword",
    "application/vnd.ms-excel",
    "application/vnd.ms-powerpoint",
}

# --- 编排逻辑 ---

def submit_document_for_processing(
    db: Session,
    document_id: uuid.UUID,
    initiator_id: uuid.UUID,
    force: bool = False,
    context: Optional[dict] = None
) -> List[Job]:
    """
    提交一个文档进行处理，采用“原位替换”策略处理内嵌文档。
    """
    context = context or {}
    jobs_created = []
    parent_document = db.query(Document).filter(Document.id == document_id).first()
    if not parent_document:
        raise ValueError(f"Document with id {document_id} not found.")

    # 如果是强制重新处理，首先清理旧的派生数据
    if force:
        # 1. 查找所有现有的子文档
        child_documents = db.query(Document).filter(Document.parent_document_id == parent_document.id).all()
        child_document_ids = [doc.id for doc in child_documents]

        # 2. (关键修复) 中止所有与这些子文档关联的正在运行的作业
        if child_document_ids:
            # We need a JobService instance to call the abort method.
            # This introduces a slight dependency, but it's the cleanest way.
            # Assuming redis_client is not strictly needed for abort_jobs_for_documents.
            job_service = JobService(db=db, redis_client=None, minio_client=None) 
            aborted_count = job_service.abort_jobs_for_documents(
                document_ids=child_document_ids,
                initiator_id=initiator_id
            )
            print(f"Force mode: Aborted {aborted_count} jobs associated with old child documents.")

        # 3. 现在可以安全地删除旧的子文档
        for child_doc in child_documents:
            db.delete(child_doc)
        
        # 4. 清理父文档的旧解析结果
        if parent_document.canonical_content:
            # 修复：通过将关系设置为 None 来触发孤立删除 (delete-orphan cascade)
            # 这比直接 delete() 更安全，能更好地让 SQLAlchemy 管理级联操作
            parent_document.canonical_content = None
        
        # 清理与资产的关联
        # 注意：asset_contexts 是一个多对多关系，使用 clear() 是正确的
        parent_document.asset_contexts.clear()
        parent_document.status = DocumentStatus.UPLOADED
        db.flush()

    original = parent_document.original
    is_container = original.detected_mime_type.endswith("wordprocessingml.document")
    
    minio = get_minio_client()
    modified_docx_storage_path = None

    # 仅当文档是容器类型，并且上下文中没有明确禁止提取时，才执行分解逻辑
    if is_container and context.get("extract_embedded_documents", True):
        try:
            # 1. 下载原始 DOCX
            bucket, object_name = parse_storage_path(original.storage_path)
            response = minio.get_object(bucket, object_name)
            docx_content = response.read()

            # 2. 分解并获取带有占位符的修改后内容
            modified_content, embedded_files_info = decompose_docx_and_replace_ole(
                parent_document.original_filename, docx_content
            )
            
            placeholder_to_child_id = {}
            # 解决方案：引入一个本地缓存，追踪在本次事务中已处理的 Original ID 及其对应的 Document ID
            processed_originals_in_transaction = {}

            # 3. 过滤并处理内嵌文件
            mime_whitelist = get_mime_whitelist()
            skip_legacy = should_skip_legacy_office()

            for file_info in embedded_files_info:
                # 新增：在处理前，尝试解包 OLE 封装
                unwrapped_content, new_filename, new_mime_type = unwrap_ole_and_correct_info(
                    content=file_info['content'],
                    filename=file_info['filename'],
                    mime_type=file_info['mime_type']
                )
                
                # 使用可能已更新的信息
                file_content = unwrapped_content
                filename_lower = new_filename.lower()
                mime_type = new_mime_type.lower()
                
                # 步骤 3a: 在创建任何数据库记录之前，首先进行严格的类型检查
                # 新增：严格排除 .bin 文件
                if filename_lower.endswith('.bin'):
                    print(f"  - SKIPPING embedded file '{new_filename}' due to .bin extension after unwrap attempt.")
                    continue

                is_whitelisted = mime_whitelist is None or mime_type in mime_whitelist
                is_legacy_office_skipped = skip_legacy and mime_type in LEGACY_OFFICE_MIMES

                if not is_whitelisted or is_legacy_office_skipped:
                    reason = "MIME type not in whitelist" if not is_whitelisted else "Skipping legacy Office format"
                    print(f"  - SKIPPING embedded file '{new_filename}' ({mime_type}). Reason: {reason}.")
                    continue

                # 步骤 3b: 只有通过检查的文件，才为其创建数据库记录
                # 获取或创建 Original 记录 (内容去重)
                child_original = create_or_get_original(
                    db=db,
                    contents=file_content,
                    filename=new_filename,
                    reported_mime_type=new_mime_type
                )
                
                child_document = None
                # 关键修复：首先检查本地事务缓存
                if child_original.id in processed_originals_in_transaction:
                    child_document_id = processed_originals_in_transaction[child_original.id]
                    child_document = db.query(Document).get(child_document_id)
                    print(f"  - Reusing document {child_document.id} for original {child_original.id} from current transaction.")

                if not child_document:
                    # 在知识空间内检查此 Original 是否已被文档关联 (知识空间内文档去重)
                    existing_document = db.query(Document).filter(
                        Document.knowledge_space_id == parent_document.knowledge_space_id,
                        Document.original_id == child_original.id
                    ).first()

                    if existing_document:
                        child_document = existing_document
                        print(f"  - Reusing existing document record {child_document.id} for original {child_original.id}, status: {child_document.status}")
                    
                if child_document:
                    # 将找到的文档（无论是来自缓存还是数据库）记录到事务缓存中
                    processed_originals_in_transaction[child_original.id] = child_document.id
                    should_create_job = False
                    if force:
                        print(f"  - Force mode enabled, creating new job for document {child_document.id}.")
                        should_create_job = True
                    elif child_document.status not in [DocumentStatus.PROCESSED, DocumentStatus.PENDING, DocumentStatus.RUNNING]:
                        print(f"  - Document {child_document.id} status is '{child_document.status}', creating new job.")
                        should_create_job = True
                    else:
                        print(f"  - Document {child_document.id} status is '{child_document.status}', no new job needed.")

                    if should_create_job:
                        child_job = create_document_processing_job(db, child_document.id, initiator_id, force=force)
                        jobs_created.append(child_job)
                else:
                    # 创建新的文档记录，并始终为其创建处理作业
                    new_child_document = create_document_record(
                        db=db,
                        knowledge_space_id=parent_document.knowledge_space_id,
                        original_id=child_original.id,
                        original_filename=file_info['filename'],
                        uploader_id=initiator_id,
                        parent_document_id=parent_document.id
                    )
                    db.flush() # 确保 ID 可用
                    print(f"  - Created new document record {new_child_document.id} for original {child_original.id}")
                    # 将新创建的文档记录到事务缓存中
                    processed_originals_in_transaction[child_original.id] = new_child_document.id
                    child_document = new_child_document
                    
                    child_job = create_document_processing_job(db, child_document.id, initiator_id, force=force)
                    jobs_created.append(child_job)

                placeholder_to_child_id[file_info['placeholder_id']] = child_document.id

            # 4. 将占位符替换为最终的链接标签
            final_content_str = modified_content.decode('latin1') # Use latin1 to avoid unicode errors with binary data
            for placeholder, child_id in placeholder_to_child_id.items():
                child_doc = db.query(Document).get(child_id)
                link_tag = f'[kosmos-embed: id={child_id}, filename="{child_doc.original_filename}"]'
                final_content_str = final_content_str.replace(f"[[KOSMOS_EMBED_PLACEHOLDER:{placeholder}]]", link_tag)
            
            final_content_bytes = final_content_str.encode('latin1')

            # 5. 上传修改后的 DOCX
            modified_hash = hashlib.sha256(final_content_bytes).hexdigest()
            modified_object_name = f"{modified_hash}.docx"
            modified_docx_storage_path = f"/{settings.MINIO_BUCKET_CANONICAL_CONTENTS}/{modified_object_name}"
            
            minio.put_object(
                settings.MINIO_BUCKET_CANONICAL_CONTENTS,
                modified_object_name,
                BytesIO(final_content_bytes),
                len(final_content_bytes),
                content_type=original.detected_mime_type
            )

        except Exception as e:
            print(f"错误: 分解容器文档 {parent_document.id} 失败: {e}")
            # Fallback or error logging
    
    # 6. 创建父文档的处理作业
    parent_job_context = {}
    if modified_docx_storage_path:
        parent_job_context['modified_docx_path'] = modified_docx_storage_path

    parent_job = create_document_processing_job(db, parent_document.id, initiator_id, force=force)
    parent_job.context = parent_job_context
    jobs_created.insert(0, parent_job)

    return jobs_created


