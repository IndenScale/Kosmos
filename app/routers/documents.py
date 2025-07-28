from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

import os
from app.db.database import get_db
from app.models.user import User
from app.models.document import Document
from app.schemas.document import DocumentResponse, KBDocumentResponse, DocumentListResponse, BatchDeleteRequest, BatchDeleteResponse
from app.services.document_service import DocumentService
from app.dependencies.auth import get_current_user
from app.dependencies.kb_auth import get_kb_admin_or_owner, get_kb_member, get_kb_or_public, get_kb_document_access
from app.models.fragment import Fragment
from app.models.index import Index
from app.config import UploadConfig
from sqlalchemy import func

router = APIRouter(prefix="/api/v1/kbs", tags=["documents"])


@router.post("/{kb_id}/documents", response_model=DocumentResponse)
def upload_document(
    kb_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_kb_document_access),
    db: Session = Depends(get_db)
):
    """上传文档到知识库"""
    
    # 验证文件是否被支持
    if not UploadConfig.is_supported_file(file.filename, file.content_type):
        supported_extensions = ", ".join(sorted(UploadConfig.get_supported_extensions()))
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型。支持的格式：{supported_extensions}"
        )

    # 验证文件大小
    if file.size:
        is_valid, error_message = UploadConfig.validate_file_size(
            file.filename, file.size, file.content_type
        )
        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail=error_message
            )

    doc_service = DocumentService(db)

    try:
        document = doc_service.upload_document(kb_id, current_user.id, file)

        # 重新查询文档以确保加载所有关联数据
        from sqlalchemy.orm import joinedload
        document_with_relations = db.query(Document).options(
            joinedload(Document.physical_file)
        ).filter(Document.id == document.id).first()

        # 手动构建响应数据，根据用户权限决定是否返回文件URL
        response_data = {
            "id": document_with_relations.id,
            "filename": document_with_relations.filename,
            "file_type": document_with_relations.file_type,
            "created_at": document_with_relations.created_at,
            "file_size": document_with_relations.physical_file.file_size if document_with_relations.physical_file else 0,
            "file_url": doc_service._get_safe_file_url(document_with_relations.physical_file, current_user)
        }

        return DocumentResponse(**response_data)

    except Exception as e:
        # 记录错误日志
        import logging
        logging.error(f"文档上传失败: {str(e)}")

        # 返回具体的错误信息
        if "duplicate" in str(e).lower() or "unique" in str(e).lower():
            raise HTTPException(
                status_code=409,
                detail="文档已存在于该知识库中"
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"文档上传失败: {str(e)}"
            )

@router.get("/{kb_id}/documents", response_model=DocumentListResponse)
def list_documents(
    kb_id: str,
    current_user: User = Depends(get_kb_or_public),
    db: Session = Depends(get_db)
):
    """列出知识库中的所有文档"""
    doc_service = DocumentService(db)
    documents_data = doc_service.get_kb_documents_with_chunk_count(kb_id, current_user)

    documents = [KBDocumentResponse.model_validate(doc_data) for doc_data in documents_data]

    return DocumentListResponse(
        documents=documents,
        total=len(documents)
    )

@router.get("/{kb_id}/documents/{document_id}", response_model=KBDocumentResponse)
def get_document(
    kb_id: str,
    document_id: str,
    current_user: User = Depends(get_kb_or_public),
    db: Session = Depends(get_db)
):
    """获取文档元数据"""
    doc_service = DocumentService(db)
    kb_document = doc_service.get_kb_document(kb_id, document_id)

    if not kb_document:
        raise HTTPException(status_code=404, detail="文档不存在")

    # 手动构建响应数据，确保包含 file_size 和 file_url
    response_data = {
        "kb_id": kb_document.kb_id,
        "document_id": kb_document.document_id,
        "upload_at": kb_document.upload_at,
        "last_ingest_time": kb_document.last_ingest_time,
        "document": {
            "id": kb_document.document.id,
            "filename": kb_document.document.filename,
            "file_type": kb_document.document.file_type,
            "created_at": kb_document.document.created_at,
            "file_size": kb_document.document.physical_file.file_size if kb_document.document.physical_file else 0,
            "file_url": doc_service._get_safe_file_url(kb_document.document.physical_file, current_user)
        },
        "chunk_count": 0,  # 暂时设为0，等摄入功能重构后再实现
        "uploader_username": kb_document.document.uploader.username if kb_document.document.uploader else None,
        "is_index_outdated": False  # 暂时设为False
    }

    return KBDocumentResponse.model_validate(response_data)

@router.get("/{kb_id}/documents/{document_id}/download")
def download_document(
    kb_id: str,
    document_id: str,
    current_user: User = Depends(get_kb_document_access),
    db: Session = Depends(get_db)
):
    """下载原始文档文件"""
    doc_service = DocumentService(db)

    # 验证文档存在于该知识库中
    kb_document = doc_service.get_kb_document(kb_id, document_id)
    if not kb_document:
        raise HTTPException(status_code=404, detail="文档不存在")

    # 获取文件路径
    file_path = doc_service.get_document_file_path(document_id)
    if not file_path:
        raise HTTPException(status_code=404, detail="文件不存在")

    return FileResponse(
        path=file_path,
        filename=kb_document.document.filename,
        media_type=kb_document.document.file_type
    )

@router.delete("/{kb_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_document(
    kb_id: str,
    document_id: str,
    current_user: User = Depends(get_current_user),
    kb_member = Depends(get_kb_admin_or_owner),
    db: Session = Depends(get_db)
):
    """从知识库中移除文档"""
    doc_service = DocumentService(db)

    try:
        success = doc_service.remove_document_from_kb(kb_id, document_id)
        if not success:
            raise HTTPException(status_code=404, detail="文档不存在")
    except Exception as e:
        # 记录错误日志
        import logging
        logging.error(f"删除文档失败: kb_id={kb_id}, document_id={document_id}, 错误: {str(e)}")
        
        # 返回具体的错误信息
        raise HTTPException(
            status_code=500,
            detail=f"删除文档失败: {str(e)}"
        )

@router.delete("/{kb_id}/documents/batch", response_model=BatchDeleteResponse)
def batch_remove_documents(
    kb_id: str,
    request: BatchDeleteRequest,
    current_user: User = Depends(get_current_user),
    kb_member = Depends(get_kb_admin_or_owner),
    db: Session = Depends(get_db)
):
    """批量从知识库中移除文档"""
    if not request.document_ids:
        raise HTTPException(
            status_code=400,
            detail="文档ID列表不能为空"
        )

    if len(request.document_ids) > 100:  # 限制批量操作数量
        raise HTTPException(
            status_code=400,
            detail="单次批量删除文档数量不能超过100个"
        )

    doc_service = DocumentService(db)
    
    try:
        results = doc_service.remove_documents_from_kb(kb_id, request.document_ids)

        success_count = sum(1 for success in results.values() if success)
        failed_count = len(results) - success_count

        return BatchDeleteResponse(
            results=results,
            success_count=success_count,
            failed_count=failed_count
        )
    except Exception as e:
        # 记录错误日志
        import logging
        logging.error(f"批量删除文档失败: kb_id={kb_id}, 错误: {str(e)}")
        
        raise HTTPException(
            status_code=500,
            detail=f"批量删除文档失败: {str(e)}"
        )

@router.get("/{kb_id}/documents/{document_id}/status")
def get_document_status(
    kb_id: str,
    document_id: str,
    current_user: User = Depends(get_kb_or_public),
    db: Session = Depends(get_db)
):
    """获取文档的fragment和index状态"""
    doc_service = DocumentService(db)
    
    # 验证文档存在于该知识库中
    kb_document = doc_service.get_kb_document(kb_id, document_id)
    if not kb_document:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    # 获取文档的文本fragment数量（只统计可索引的文本类型）
    fragment_count = db.query(func.count(Fragment.id)).filter(
        Fragment.document_id == document_id,
        Fragment.fragment_type == 'text'
    ).scalar() or 0
    
    # 获取已索引的文本fragment数量
    indexed_count = db.query(func.count(Index.id)).join(
        Fragment, Fragment.id == Index.fragment_id
    ).filter(
        Fragment.document_id == document_id,
        Fragment.fragment_type == 'text'
    ).scalar() or 0
    
    return {
        "document_id": document_id,
        "fragment_count": fragment_count,
        "indexed_count": indexed_count,
        "status": "not_parsed" if fragment_count == 0 else (
            "completed" if fragment_count == indexed_count and fragment_count > 0 else "indexing"
        ),
        "progress": 0 if fragment_count == 0 else (indexed_count / fragment_count * 100)
    }

@router.get("/{kb_id}/documents/status/batch")
def get_documents_status_batch(
    kb_id: str,
    current_user: User = Depends(get_kb_or_public),
    db: Session = Depends(get_db)
):
    """批量获取知识库中所有文档的fragment和index状态"""
    doc_service = DocumentService(db)
    
    # 获取知识库中的所有文档
    documents_data = doc_service.get_kb_documents_with_chunk_count(kb_id, current_user)
    
    # 批量查询所有文档的fragment和index统计
    document_ids = [doc['document']['id'] for doc in documents_data]
    
    # 查询每个文档的文本fragment数量（只统计可索引的文本类型）
    fragment_stats = db.query(
        Fragment.document_id,
        func.count(Fragment.id).label('fragment_count')
    ).filter(
        Fragment.document_id.in_(document_ids),
        Fragment.fragment_type == 'text'
    ).group_by(Fragment.document_id).all()
    
    # 查询每个文档的已索引文本fragment数量
    indexed_stats = db.query(
        Fragment.document_id,
        func.count(Index.id).label('indexed_count')
    ).join(
        Index, Fragment.id == Index.fragment_id
    ).filter(
        Fragment.document_id.in_(document_ids),
        Fragment.fragment_type == 'text'
    ).group_by(Fragment.document_id).all()
    
    # 构建统计字典
    fragment_counts = {stat.document_id: stat.fragment_count for stat in fragment_stats}
    indexed_counts = {stat.document_id: stat.indexed_count for stat in indexed_stats}
    
    # 构建结果
    results = {}
    for doc_id in document_ids:
        fragment_count = fragment_counts.get(doc_id, 0)
        indexed_count = indexed_counts.get(doc_id, 0)
        
        status = "not_parsed" if fragment_count == 0 else (
            "completed" if fragment_count == indexed_count and fragment_count > 0 else "indexing"
        )
        progress = 0 if fragment_count == 0 else (indexed_count / fragment_count * 100)
        
        results[doc_id] = {
            "document_id": doc_id,
            "fragment_count": fragment_count,
            "indexed_count": indexed_count,
            "status": status,
            "progress": progress
        }
    
    return results
