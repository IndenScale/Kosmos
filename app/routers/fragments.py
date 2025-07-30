"""
Fragment相关的路由
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import os
import json
from pathlib import Path

from app.db.database import get_db
from app.dependencies.kb_auth import get_kb_member, get_kb_or_public
from app.services.fragment_service import FragmentService
from app.schemas.fragment import (
    FragmentResponse, 
    FragmentListResponse, 
    FragmentUpdate,
    FragmentStatsResponse
)

router = APIRouter(prefix="/api/v1", tags=["fragments"])


@router.get("/kbs/{kb_id}/fragments", response_model=FragmentListResponse)
def get_kb_fragments(
    kb_id: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    fragment_type: Optional[str] = Query(None, description="Fragment类型过滤"),
    db: Session = Depends(get_db),
    current_user=Depends(get_kb_or_public)
):
    """获取知识库的Fragment列表"""
    fragment_service = FragmentService(db)
    return fragment_service.get_kb_fragments(
        kb_id=kb_id,
        page=page,
        page_size=page_size,
        fragment_type=fragment_type
    )


@router.get("/documents/{document_id}/fragments", response_model=List[FragmentResponse])
def get_document_fragments(
    document_id: str,
    db: Session = Depends(get_db)
):
    """获取文档的Fragment列表"""
    fragment_service = FragmentService(db)
    return fragment_service.get_document_fragments(document_id)


@router.get("/fragments/{fragment_id}", response_model=FragmentResponse)
def get_fragment(
    fragment_id: str,
    db: Session = Depends(get_db)
):
    """获取Fragment详情"""
    fragment_service = FragmentService(db)
    fragment = fragment_service.get_fragment(fragment_id)
    if not fragment:
        raise HTTPException(status_code=404, detail="Fragment not found")
    return fragment


@router.put("/fragments/{fragment_id}", response_model=FragmentResponse)
def update_fragment(
    fragment_id: str,
    fragment_update: FragmentUpdate,
    db: Session = Depends(get_db)
):
    """更新Fragment"""
    fragment_service = FragmentService(db)
    fragment = fragment_service.update_fragment(fragment_id, fragment_update)
    if not fragment:
        raise HTTPException(status_code=404, detail="Fragment not found")
    return fragment


@router.delete("/fragments/{fragment_id}")
def delete_fragment(
    fragment_id: str,
    db: Session = Depends(get_db)
):
    """删除Fragment"""
    fragment_service = FragmentService(db)
    success = fragment_service.delete_fragment(fragment_id)
    if not success:
        raise HTTPException(status_code=404, detail="Fragment not found")
    return {"message": "Fragment deleted successfully"}


@router.get("/kbs/{kb_id}/fragments/stats", response_model=FragmentStatsResponse)
def get_kb_fragment_stats(
    kb_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_kb_or_public)
):
    """获取知识库Fragment统计信息"""
    fragment_service = FragmentService(db)
    return fragment_service.get_kb_fragment_stats(kb_id)


@router.get("/fragments/{fragment_id}/image")
def get_fragment_image(
    fragment_id: str,
    db: Session = Depends(get_db)
):
    """获取Fragment关联的图片文件
    
    对于screenshot类型，从meta_info.screenshot_path获取图片路径
    对于figure类型，从meta_info.image_path获取图片路径
    """
    fragment_service = FragmentService(db)
    fragment = fragment_service.get_fragment(fragment_id)
    
    if not fragment:
        raise HTTPException(status_code=404, detail="Fragment not found")
    
    try:
        # 解析meta_info
        if isinstance(fragment.meta_info, str):
            meta_info = json.loads(fragment.meta_info)
        else:
            meta_info = fragment.meta_info or {}
        
        # 根据fragment类型获取对应的图片路径
        image_path = None
        if fragment.fragment_type == "screenshot":
            image_path = meta_info.get("screenshot_path")
        elif fragment.fragment_type == "figure":
            image_path = meta_info.get("image_path")
        
        if not image_path:
            raise HTTPException(
                status_code=404, 
                detail=f"No image path found for fragment type: {fragment.fragment_type}"
            )
        
        # 检查文件是否存在
        if not os.path.exists(image_path):
            raise HTTPException(
                status_code=404, 
                detail=f"Image file not found: {image_path}"
            )
        
        # 将本地路径转换为静态文件URL
        project_root = Path(__file__).parent.parent
        data_dir = project_root / "data"
        image_path_obj = Path(image_path)
        
        try:
            # 标准化路径，处理绝对路径和相对路径
            image_path_resolved = image_path_obj.resolve()
            data_dir_resolved = data_dir.resolve()
            
            # 计算相对于data目录的相对路径
            relative_path = image_path_resolved.relative_to(data_dir_resolved)
            static_url = f"/static/data/{relative_path}"
            
            # 返回重定向到静态文件URL
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url=static_url)
        except ValueError as e:
            # 如果路径不在data目录下，记录日志并直接返回文件响应
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Image path {image_path} is not under data directory {data_dir}: {e}")
            return FileResponse(image_path)
        
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500, 
            detail="Invalid meta_info format"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error retrieving image: {str(e)}"
        )