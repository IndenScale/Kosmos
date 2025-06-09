from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
import os
from db.database import get_db
from models.user import User
from schemas.document import DocumentResponse, KBDocumentResponse, DocumentListResponse
from services.document_service import DocumentService
from dependencies.auth import get_current_user
from dependencies.kb_auth import get_kb_admin_or_owner, get_kb_member

router = APIRouter(prefix="/api/v1/kbs", tags=["documents"])

@router.post("/{kb_id}/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def upload_document(
    kb_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    kb_member = Depends(get_kb_admin_or_owner),
    db: Session = Depends(get_db)
):
    """上传文档到知识库"""
    # 验证文件类型
    allowed_types = {
        "application/pdf",
        "text/plain",
        "text/markdown",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
        "application/octet-stream"
    }

    # 在验证类型后添加扩展名验证
    allowed_extensions = {'.pdf', '.txt', '.md', '.docx', '.doc', '.pptx'}
    file_extension = os.path.splitext(file.filename)[1].lower()

    if file.content_type in allowed_types and file_extension in allowed_extensions:
        pass
    else:
        raise HTTPException(status_code=400, detail="不支持的文件类型")

    # 验证文件大小 (10MB限制)
    max_size = 10 * 1024 * 1024
    if file.size and file.size > max_size:
        raise HTTPException(
            status_code=400,
            detail="文件大小不能超过10MB"
        )

    doc_service = DocumentService(db)
    document = doc_service.upload_document(kb_id, current_user.id, file)

    return DocumentResponse.from_orm(document)

@router.get("/{kb_id}/documents", response_model=DocumentListResponse)
def list_documents(
    kb_id: str,
    current_user: User = Depends(get_current_user),
    kb_member = Depends(get_kb_member),
    db: Session = Depends(get_db)
):
    """列出知识库中的所有文档"""
    doc_service = DocumentService(db)
    documents_data = doc_service.get_kb_documents_with_chunk_count(kb_id)
    
    documents = [KBDocumentResponse(**doc_data) for doc_data in documents_data]

    return DocumentListResponse(
        documents=documents,
        total=len(documents)
    )

@router.get("/{kb_id}/documents/{document_id}", response_model=KBDocumentResponse)
def get_document(
    kb_id: str,
    document_id: str,
    current_user: User = Depends(get_current_user),
    kb_member = Depends(get_kb_member),
    db: Session = Depends(get_db)
):
    """获取文档元数据"""
    doc_service = DocumentService(db)
    kb_document = doc_service.get_kb_document(kb_id, document_id)

    if not kb_document:
        raise HTTPException(status_code=404, detail="文档不存在")

    return KBDocumentResponse.from_orm(kb_document)

@router.get("/{kb_id}/documents/{document_id}/download")
def download_document(
    kb_id: str,
    document_id: str,
    current_user: User = Depends(get_current_user),
    kb_member = Depends(get_kb_member),
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

    success = doc_service.remove_document_from_kb(kb_id, document_id)
    if not success:
        raise HTTPException(status_code=404, detail="文档不存在")