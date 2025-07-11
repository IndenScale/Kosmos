from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.orm import Session
from typing import Dict, Any
import json

from app.db.database import get_db
from app.models.user import User
from app.services.sdtm_service import SDTMService
from app.schemas.sdtm import (
    SDTMStatsResponse, TagDictionaryOptimizeRequest, TagDictionaryOptimizeResponse,
    DocumentBatchRequest, DocumentBatchResponse
)
from app.models.sdtm import SDTMMode, SDTMJob
from app.dependencies.auth import get_current_user
from app.dependencies.kb_auth import get_kb_member, get_kb_admin_or_owner

router = APIRouter(prefix="/api/v1/sdtm", tags=["sdtm"])

@router.get("/{kb_id}/stats", response_model=SDTMStatsResponse)
async def get_sdtm_stats(
    kb_id: str = Path(..., description="知识库ID"),
    current_user: User = Depends(get_kb_member),
    db: Session = Depends(get_db)
):
    """获取知识库SDTM统计信息"""
    try:
        sdtm_service = SDTMService(db)
        stats = sdtm_service.get_kb_stats(kb_id)
        
        return SDTMStatsResponse(
            kb_id=kb_id,
            progress_metrics=stats.progress_metrics,
            quality_metrics=stats.quality_metrics,
            abnormal_documents=stats.abnormal_documents,
            last_updated=stats.last_updated
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取统计信息失败: {str(e)}"
        )

@router.post("/{kb_id}/optimize")
async def optimize_tag_dictionary(
    request: TagDictionaryOptimizeRequest,
    kb_id: str = Path(..., description="知识库ID"),
    current_user: User = Depends(get_kb_admin_or_owner),
    db: Session = Depends(get_db)
):
    """启动标签字典优化任务"""
    try:
        sdtm_service = SDTMService(db)
        
        # 启动异步任务
        job_id = await sdtm_service.start_sdtm_job(
            kb_id=kb_id,
            mode=request.mode,
            batch_size=request.batch_size,
            auto_apply=request.auto_apply,
            abnormal_doc_slots=request.abnormal_doc_slots,
            normal_doc_slots=request.normal_doc_slots,
            max_iterations=request.max_iterations,
            abnormal_doc_threshold=request.abnormal_doc_threshold,
            enable_early_termination=request.enable_early_termination
        )
        
        return {
            "success": True,
            "message": "SDTM任务已启动",
            "job_id": job_id
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"启动SDTM任务失败: {str(e)}"
        )

@router.get("/{kb_id}/jobs/{job_id}")
async def get_sdtm_job_status(
    kb_id: str = Path(..., description="知识库ID"),
    job_id: str = Path(..., description="任务ID"),
    current_user: User = Depends(get_kb_member),
    db: Session = Depends(get_db)
):
    """获取SDTM任务状态"""
    try:
        sdtm_service = SDTMService(db)
        job = sdtm_service.get_sdtm_job_status(job_id)
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )
        
        if job.kb_id != kb_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有访问此任务的权限"
            )
        
        result = None
        if job.result:
            try:
                result = json.loads(job.result)
            except:
                pass
        
        return {
            "job_id": job.id,
            "kb_id": job.kb_id,
            "mode": job.mode,
            "batch_size": job.batch_size,
            "auto_apply": job.auto_apply,
            "status": job.status,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
            "error_message": job.error_message,
            "result": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取任务状态失败: {str(e)}"
        )

@router.get("/{kb_id}/jobs")
async def get_kb_sdtm_jobs(
    kb_id: str = Path(..., description="知识库ID"),
    current_user: User = Depends(get_kb_member),
    db: Session = Depends(get_db)
):
    """获取知识库的所有SDTM任务"""
    try:
        sdtm_service = SDTMService(db)
        jobs = sdtm_service.get_kb_sdtm_jobs(kb_id)
        
        return {
            "success": True,
            "jobs": [
                {
                    "job_id": job.id,
                    "mode": job.mode,
                    "batch_size": job.batch_size,
                    "auto_apply": job.auto_apply,
                    "status": job.status,
                    "created_at": job.created_at,
                    "updated_at": job.updated_at,
                    "error_message": job.error_message
                }
                for job in jobs
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取任务列表失败: {str(e)}"
        )

@router.post("/{kb_id}/annotate")
async def batch_annotate_documents(
    request: DocumentBatchRequest,
    kb_id: str = Path(..., description="知识库ID"),
    current_user: User = Depends(get_kb_admin_or_owner),
    db: Session = Depends(get_db)
):
    """启动批量标注任务"""
    try:
        sdtm_service = SDTMService(db)
        
        # 启动异步任务
        job_id = await sdtm_service.start_sdtm_job(
            kb_id=kb_id,
            mode=request.mode,
            batch_size=10,
            auto_apply=True
        )
        
        return {
            "success": True,
            "message": "SDTM标注任务已启动",
            "job_id": job_id
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"启动SDTM标注任务失败: {str(e)}"
        )

@router.post("/{kb_id}/process")
async def process_knowledge_base(
    kb_id: str = Path(..., description="知识库ID"),
    mode: str = "edit",
    batch_size: int = 10,
    auto_apply: bool = True,
    current_user: User = Depends(get_kb_admin_or_owner),
    db: Session = Depends(get_db)
):
    """处理知识库（通用接口）"""
    try:
        from app.models.sdtm import SDTMMode
        
        # 验证模式
        if mode not in ["edit", "annotate", "shadow"]:
            raise ValueError(f"无效的模式: {mode}")
        
        sdtm_mode = SDTMMode(mode)
        sdtm_service = SDTMService(db)
        
        # 执行处理
        result = await sdtm_service.process_knowledge_base(
            kb_id=kb_id,
            mode=sdtm_mode,
            batch_size=batch_size,
            auto_apply=auto_apply
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理知识库失败: {str(e)}"
        )

@router.get("/{kb_id}/abnormal-documents")
async def get_abnormal_documents(
    kb_id: str = Path(..., description="知识库ID"),
    current_user: User = Depends(get_kb_member),
    db: Session = Depends(get_db)
):
    """获取异常文档列表"""
    try:
        sdtm_service = SDTMService(db)
        stats = sdtm_service.get_kb_stats(kb_id)
        
        return {
            "success": True,
            "abnormal_documents": stats.abnormal_documents,
            "total_count": len(stats.abnormal_documents)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取异常文档失败: {str(e)}"
        )

@router.post("/{kb_id}/shadow-mode")
async def run_shadow_mode(
    kb_id: str = Path(..., description="知识库ID"),
    batch_size: int = 10,
    current_user: User = Depends(get_kb_admin_or_owner),
    db: Session = Depends(get_db)
):
    """运行影子模式，监测语义漂移"""
    try:
        from app.models.sdtm import SDTMMode
        
        sdtm_service = SDTMService(db)
        
        # 执行影子模式
        result = await sdtm_service.process_knowledge_base(
            kb_id=kb_id,
            mode=SDTMMode.SHADOW,
            batch_size=batch_size,
            auto_apply=False  # 影子模式不应用任何操作
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"运行影子模式失败: {str(e)}"
        )

@router.post("/{kb_id}/cold-start")
async def run_cold_start(
    kb_id: str = Path(..., description="知识库ID"),
    batch_size: int = 10,
    auto_apply: bool = True,
    current_user: User = Depends(get_kb_admin_or_owner),
    db: Session = Depends(get_db)
):
    """运行SDTM冷启动，直接分析未摄入的文档"""
    try:
        from app.models.sdtm import SDTMMode
        
        sdtm_service = SDTMService(db)
        
        # 执行冷启动模式（使用编辑模式）
        result = await sdtm_service.process_knowledge_base(
            kb_id=kb_id,
            mode=SDTMMode.EDIT,
            batch_size=batch_size,
            auto_apply=auto_apply
        )
        
        # 添加冷启动特殊标识
        result["cold_start"] = True
        result["message"] = f"冷启动完成: {result.get('message', '')}"
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"冷启动失败: {str(e)}"
        ) 