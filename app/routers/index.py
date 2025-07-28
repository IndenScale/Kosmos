from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.database import get_db
from app.schemas.index import (
    IndexRequest, BatchIndexByFragmentsRequest, BatchIndexByDocumentsRequest, 
    BatchIndexRequest, IndexResponse, IndexJobResponse, IndexStatsResponse, IndexProgressResponse
)
from app.schemas.job import JobResponse
from app.services.index_service import IndexService
from app.models.fragment import Fragment, KBFragment
from app.models.document import Document, KBDocument

router = APIRouter(prefix="/api/v1/index", tags=["index"])

@router.post("/fragment/{fragment_id}", response_model=IndexResponse)
async def create_fragment_index(
    fragment_id: str,
    request: IndexRequest = IndexRequest(),
    db: Session = Depends(get_db)
):
    """为单个Fragment创建索引"""
    # 获取Fragment及其关联的知识库ID
    fragment = db.query(Fragment).filter(Fragment.id == fragment_id).first()
    if not fragment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fragment not found"
        )

    # 通过KBFragment获取kb_id
    kb_fragment = db.query(KBFragment).filter(KBFragment.fragment_id == fragment_id).first()
    if not kb_fragment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fragment not associated with any knowledge base"
        )

    kb_id = kb_fragment.kb_id

    # 创建索引服务
    index_service = IndexService(kb_id, db)

    try:
        result = await index_service.create_fragment_index(
            fragment_id=fragment_id,
            force_regenerate=request.force_regenerate,
            max_tags=request.max_tags
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"索引创建失败: {str(e)}"
        )

@router.post("/batch/fragments", response_model=JobResponse)
async def create_batch_index_by_fragments(
    request: BatchIndexByFragmentsRequest,
    db: Session = Depends(get_db)
):
    """基于Fragment ID列表批量创建索引（使用任务队列）"""
    if not request.fragment_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fragment IDs list cannot be empty"
        )

    # 获取第一个Fragment的kb_id（假设所有Fragment都属于同一个知识库）
    kb_fragment = db.query(KBFragment).filter(KBFragment.fragment_id == request.fragment_ids[0]).first()
    if not kb_fragment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fragment not associated with any knowledge base"
        )

    kb_id = kb_fragment.kb_id

    # 验证所有Fragment都属于同一个知识库
    for fragment_id in request.fragment_ids:
        kb_frag = db.query(KBFragment).filter(KBFragment.fragment_id == fragment_id).first()
        if not kb_frag or kb_frag.kb_id != kb_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"All fragments must belong to the same knowledge base"
            )

    try:
        from app.services.unified_job_service import unified_job_service
        from app.models.job import Job, Task, JobType, TaskType, TargetType
        import uuid
        
        # 创建Job
        job = Job(
            id=str(uuid.uuid4()),
            kb_id=kb_id,
            job_type=JobType.BATCH_INDEX.value,
            total_tasks=len(request.fragment_ids)
        )
        # 设置配置
        job.config_dict = {
            "force_regenerate": request.force_regenerate,
            "max_tags": request.max_tags,
            "enable_multimodal": request.enable_multimodal,
            "multimodal_config": request.multimodal_config
        }
        db.add(job)
        db.flush()  # 获取job.id
        
        # 创建Tasks
        tasks = []
        for fragment_id in request.fragment_ids:
            task = Task(
                id=str(uuid.uuid4()),
                job_id=job.id,
                task_type=TaskType.INDEX_FRAGMENT.value,
                target_id=fragment_id,
                target_type=TargetType.FRAGMENT.value
            )
            # 设置任务配置
            task.config_dict = {
                "force_regenerate": request.force_regenerate,
                "max_tags": request.max_tags,
                "enable_multimodal": request.enable_multimodal,
                "multimodal_config": request.multimodal_config
            }
            tasks.append(task)
            db.add(task)
        
        db.commit()
        
        # 提交到任务队列
        await unified_job_service.submit_job(job, tasks, db)
        
        # 返回JobResponse
        return JobResponse(
            id=job.id,
            kb_id=job.kb_id,
            job_type=job.job_type,
            status=job.status,
            priority=job.priority,
            config=job.config_dict,
            total_tasks=job.total_tasks,
            completed_tasks=job.completed_tasks,
            failed_tasks=job.failed_tasks,
            progress_percentage=job.progress_percentage,
            error_message=job.error_message,
            created_at=job.created_at,
            updated_at=job.updated_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            created_by=job.created_by
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量索引创建失败: {str(e)}"
        )

@router.post("/batch/documents", response_model=JobResponse)
async def create_batch_index_by_documents(
    request: BatchIndexByDocumentsRequest,
    db: Session = Depends(get_db)
):
    """基于Document ID列表批量创建索引（使用任务队列，自动处理解析）"""
    if not request.document_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document IDs list cannot be empty"
        )

    # 获取第一个文档的kb_id（假设所有文档都属于同一个知识库）
    first_document = db.query(Document).filter(Document.id == request.document_ids[0]).first()
    if not first_document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {request.document_ids[0]} not found"
        )

    # 通过KBDocument获取kb_id
    kb_document = db.query(KBDocument).filter(KBDocument.document_id == request.document_ids[0]).first()
    if not kb_document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not associated with any knowledge base"
        )

    kb_id = kb_document.kb_id

    # 验证所有文档都属于同一个知识库
    for document_id in request.document_ids:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} not found"
            )
        
        kb_doc = db.query(KBDocument).filter(KBDocument.document_id == document_id).first()
        if not kb_doc or kb_doc.kb_id != kb_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"All documents must belong to the same knowledge base"
            )

    try:
        from app.services.unified_job_service import unified_job_service
        from app.models.job import Job, Task, JobType, TaskType, TargetType
        import uuid
        
        # 检查哪些文档需要解析，哪些可以直接索引
        documents_to_parse = []
        documents_to_index = []
        
        for document_id in request.document_ids:
            # 检查文档是否已有Fragment
            fragments = db.query(Fragment).filter(
                Fragment.document_id == document_id,
                Fragment.fragment_type == "text"
            ).all()
            
            if not fragments:
                # 需要先解析
                documents_to_parse.append(document_id)
            else:
                # 可以直接索引
                documents_to_index.append(document_id)
        
        # 计算总任务数：解析任务 + 索引任务
        total_tasks = len(documents_to_parse)
        if documents_to_index:
            # 为已有Fragment的文档计算索引任务数
            for document_id in documents_to_index:
                fragments = db.query(Fragment).filter(
                    Fragment.document_id == document_id,
                    Fragment.fragment_type == "text"
                ).all()
                total_tasks += len(fragments)
        
        # 创建Job
        job = Job(
            id=str(uuid.uuid4()),
            kb_id=kb_id,
            job_type=JobType.BATCH_INDEX.value,
            total_tasks=total_tasks
        )
        # 设置配置
        job.config_dict = {
            "force_regenerate": request.force_regenerate,
            "max_tags": request.max_tags,
            "enable_multimodal": request.enable_multimodal,
            "multimodal_config": request.multimodal_config,
            "source_type": "documents",  # 标记这是来自文档的索引任务
            "source_document_ids": request.document_ids,
            "documents_to_parse": documents_to_parse,
            "documents_to_index": documents_to_index
        }
        db.add(job)
        db.flush()  # 获取job.id
        
        # 创建Tasks
        tasks = []
        
        # 1. 为需要解析的文档创建解析+索引任务
        for document_id in documents_to_parse:
            # 创建解析任务，任务完成后会自动触发索引
            task = Task(
                id=str(uuid.uuid4()),
                job_id=job.id,
                task_type=TaskType.PARSE_AND_INDEX_DOCUMENT.value,  # 新的任务类型
                target_id=document_id,
                target_type=TargetType.DOCUMENT.value
            )
            # 设置任务配置
            task.config_dict = {
                "force_reparse": True,  # 确保解析
                "force_regenerate": request.force_regenerate,
                "max_tags": request.max_tags,
                "enable_multimodal": request.enable_multimodal,
                "multimodal_config": request.multimodal_config
            }
            tasks.append(task)
            db.add(task)
        
        # 2. 为已有Fragment的文档创建索引任务
        for document_id in documents_to_index:
            fragments = db.query(Fragment).filter(
                Fragment.document_id == document_id,
                Fragment.fragment_type == "text"
            ).all()
            
            for fragment in fragments:
                task = Task(
                    id=str(uuid.uuid4()),
                    job_id=job.id,
                    task_type=TaskType.INDEX_FRAGMENT.value,
                    target_id=fragment.id,
                    target_type=TargetType.FRAGMENT.value
                )
                # 设置任务配置
                task.config_dict = {
                    "force_regenerate": request.force_regenerate,
                    "max_tags": request.max_tags,
                    "enable_multimodal": request.enable_multimodal,
                    "multimodal_config": request.multimodal_config
                }
                tasks.append(task)
                db.add(task)
        
        db.commit()
        
        # 提交到任务队列
        await unified_job_service.submit_job(job, tasks, db)
        
        # 返回JobResponse
        return JobResponse(
            id=job.id,
            kb_id=job.kb_id,
            job_type=job.job_type,
            status=job.status,
            priority=job.priority,
            config=job.config_dict,
            total_tasks=job.total_tasks,
            completed_tasks=job.completed_tasks,
            failed_tasks=job.failed_tasks,
            progress_percentage=job.progress_percentage,
            error_message=job.error_message,
            created_at=job.created_at,
            updated_at=job.updated_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            created_by=job.created_by
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量索引创建失败: {str(e)}"
        )

# 保持向后兼容性的别名端点
@router.post("/batch", response_model=JobResponse)
async def create_batch_index_legacy(
    request: BatchIndexRequest,
    db: Session = Depends(get_db)
):
    """批量创建索引（向后兼容接口，使用任务队列）"""
    if request.fragment_ids:
        # 转换为BatchIndexByFragmentsRequest
        fragments_request = BatchIndexByFragmentsRequest(
            fragment_ids=request.fragment_ids,
            force_regenerate=request.force_regenerate,
            max_tags=request.max_tags,
            enable_multimodal=request.enable_multimodal,
            multimodal_config=request.multimodal_config
        )
        return await create_batch_index_by_fragments(fragments_request, db)
    elif request.document_ids:
        # 转换为BatchIndexByDocumentsRequest
        documents_request = BatchIndexByDocumentsRequest(
            document_ids=request.document_ids,
            force_regenerate=request.force_regenerate,
            max_tags=request.max_tags,
            enable_multimodal=request.enable_multimodal,
            multimodal_config=request.multimodal_config
        )
        return await create_batch_index_by_documents(documents_request, db)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either fragment_ids or document_ids must be provided"
        )

@router.get("/kb/{kb_id}/stats", response_model=IndexStatsResponse)
async def get_index_stats(
    kb_id: str,
    db: Session = Depends(get_db)
):
    """获取知识库索引统计"""
    index_service = IndexService(kb_id, db)
    
    try:
        stats = await index_service.get_index_stats()
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取索引统计失败: {str(e)}"
        )

@router.delete("/fragment/{fragment_id}")
async def delete_fragment_index(
    fragment_id: str,
    db: Session = Depends(get_db)
):
    """删除Fragment索引"""
    # 获取Fragment的kb_id
    kb_fragment = db.query(KBFragment).filter(KBFragment.fragment_id == fragment_id).first()
    if not kb_fragment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fragment not found or not associated with any knowledge base"
        )
    
    kb_id = kb_fragment.kb_id
    index_service = IndexService(kb_id, db)
    
    try:
        await index_service.delete_fragment_index(fragment_id)
        return {"message": "Fragment index deleted successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除Fragment索引失败: {str(e)}"
        )

@router.delete("/document/{document_id}")
async def delete_document_index(
    document_id: str,
    db: Session = Depends(get_db)
):
    """删除文档的所有索引"""
    # 获取文档的kb_id
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # 通过KBDocument获取kb_id
    kb_document = db.query(KBDocument).filter(KBDocument.document_id == document_id).first()
    if not kb_document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not associated with any knowledge base"
        )
    
    kb_id = kb_document.kb_id
    index_service = IndexService(kb_id, db)
    
    try:
        await index_service.delete_document_index(document_id)
        return {"message": "Document index deleted successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除文档索引失败: {str(e)}"
        )

@router.get("/kb/{kb_id}/fragments", response_model=List[IndexResponse])
async def list_indexed_fragments(
    kb_id: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """列出已索引的Fragment"""
    index_service = IndexService(kb_id, db)
    
    try:
        fragments = await index_service.list_indexed_fragments(skip=skip, limit=limit)
        return fragments
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取已索引Fragment列表失败: {str(e)}"
        )

@router.post("/cleanup/orphan-indexes")
async def cleanup_orphan_indexes(
    db: Session = Depends(get_db)
):
    """清理孤立的索引记录
    
    删除那些指向无效fragment_id或无效kb_id的索引记录
    
    Returns:
        清理统计信息
    """
    try:
        # 使用一个临时的kb_id，因为IndexService需要kb_id参数
        # 但cleanup_orphan_indexes会处理所有知识库的索引
        temp_kb_id = "temp"
        index_service = IndexService(temp_kb_id, db)
        
        cleanup_stats = await index_service.cleanup_orphan_indexes()
        
        return cleanup_stats
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"清理孤立索引记录失败: {str(e)}"
        )