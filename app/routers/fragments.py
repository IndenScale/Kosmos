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
    FragmentStatsResponse,
    FragmentType
)
from app.models import Document

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

    # 将字符串转换为FragmentType枚举
    parsed_fragment_type = None
    if fragment_type:
        try:
            parsed_fragment_type = FragmentType(fragment_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"无效的fragment类型: {fragment_type}. 有效值: {[t.value for t in FragmentType]}"
            )

    return fragment_service.get_kb_fragments(
        kb_id=kb_id,
        page=page,
        page_size=page_size,
        fragment_type=parsed_fragment_type
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
    include_metadata: bool = Query(False, description="是否包含文档信息和页码"),
    include_image_data: bool = Query(True, description="是否包含图片数据(base64编码)"),
    db: Session = Depends(get_db)
):
    """获取Fragment关联的图片文件

    如果include_metadata=true，返回包含文档名称、页码等信息的JSON响应
    include_image_data=false时，不包含图片数据，仅返回元数据信息
    """
    fragment_service = FragmentService(db)
    fragment = fragment_service.get_fragment(fragment_id)

    if not fragment:
        raise HTTPException(status_code=404, detail="Fragment not found")

    if include_metadata:
        # 获取文档信息
        document = db.query(Document).filter(Document.id == fragment.document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        # 解析meta_info获取页码信息
        try:
            if isinstance(fragment.meta_info, str):
                meta_info = json.loads(fragment.meta_info)
            else:
                meta_info = fragment.meta_info or {}
        except json.JSONDecodeError:
            meta_info = {}

        # 获取图片路径
        image_path = None
        if fragment.fragment_type == FragmentType.SCREENSHOT:
            image_path = meta_info.get("screenshot_path") or meta_info.get("image_path")
        elif fragment.fragment_type == FragmentType.FIGURE:
            image_path = meta_info.get("image_path")

        # 读取图片数据（仅在需要时）
        image_data = None
        if include_image_data and image_path and os.path.exists(image_path):
            import base64
            with open(image_path, 'rb') as f:
                image_bytes = f.read()
                image_data = base64.b64encode(image_bytes).decode('utf-8')

        # 构建响应
        response_data = {
            "id": fragment.id,
            "source_document_name": document.filename,
            "document_id": fragment.document_id,
            "fragment_type": fragment.fragment_type.value,
            "page_start": meta_info.get("page_start"),
            "page_end": meta_info.get("page_end"),
            "page_number": meta_info.get("page_number"),
            "fragment_index": fragment.fragment_index,
            "image_data": image_data,  # 可能为None
            "created_at": fragment.created_at,
            "updated_at": fragment.updated_at
        }

        return response_data
    else:
        # 原有逻辑：直接返回图片文件
        try:
            # 解析meta_info
            if isinstance(fragment.meta_info, str):
                meta_info = json.loads(fragment.meta_info)
            else:
                meta_info = fragment.meta_info or {}

            # 根据fragment类型获取对应的图片路径
            image_path = None
            if fragment.fragment_type == FragmentType.SCREENSHOT:
                # 兼容现有数据：先尝试screenshot_path，如果没有则使用image_path
                image_path = meta_info.get("screenshot_path") or meta_info.get("image_path")
            elif fragment.fragment_type == FragmentType.FIGURE:
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


# 兼容老接口的截图路由
# 添加新的截图端点，支持返回metadata
@router.get("/screenshots/{screenshot_id}/metadata")
def get_screenshot_metadata(
    screenshot_id: str,
    db: Session = Depends(get_db)
):
    """获取截图的metadata信息

    返回fragment的完整信息，包括metadata
    """
    fragment_service = FragmentService(db)
    fragment = fragment_service.get_fragment(screenshot_id)

    if not fragment:
        raise HTTPException(status_code=404, detail="Screenshot not found")

    # 确保是screenshot类型
    if fragment.fragment_type != FragmentType.SCREENSHOT:
        raise HTTPException(
            status_code=400,
            detail=f"Fragment {screenshot_id} is not a screenshot type"
        )

    return {
        "id": fragment.id,
        "content_hash": fragment.content_hash,
        "document_id": fragment.document_id,
        "fragment_index": fragment.fragment_index,
        "fragment_type": fragment.fragment_type.value,
        "raw_content": fragment.raw_content,
        "meta_info": fragment.meta_info,
        "created_at": fragment.created_at,
        "updated_at": fragment.updated_at
    }

# 修改现有的截图端点，添加可选的metadata参数
@router.get("/screenshots/{screenshot_id}/image")
def get_screenshot_legacy(
    screenshot_id: str,
    task_id: Optional[str] = Query(None, description="任务ID（兼容参数，暂不使用）"),
    include_metadata: bool = Query(False, description="是否包含metadata信息"),
    db: Session = Depends(get_db)
):
    """兼容老版本截图接口

    这个接口是为了兼容评估系统的老请求格式：
    /screenshots/{screenshot_id}/image?task_id=xxx

    如果include_metadata=true，则返回包含metadata的JSON响应
    否则返回图片文件
    """
    if include_metadata:
        # 返回metadata和图片数据
        fragment_service = FragmentService(db)
        fragment = fragment_service.get_fragment(screenshot_id)

        if not fragment:
            raise HTTPException(status_code=404, detail="Screenshot not found")

        # 获取图片数据
        try:
            if isinstance(fragment.meta_info, str):
                meta_info = json.loads(fragment.meta_info)
            else:
                meta_info = fragment.meta_info or {}

            image_path = meta_info.get("screenshot_path") or meta_info.get("image_path")
            image_data = None

            if image_path and os.path.exists(image_path):
                import base64
                with open(image_path, 'rb') as f:
                    image_bytes = f.read()
                    image_data = base64.b64encode(image_bytes).decode('utf-8')

            return {
                "id": fragment.id,
                "content_hash": fragment.content_hash,
                "document_id": fragment.document_id,
                "fragment_index": fragment.fragment_index,
                "fragment_type": fragment.fragment_type.value,
                "raw_content": fragment.raw_content,
                "meta_info": fragment.meta_info,
                "created_at": fragment.created_at,
                "updated_at": fragment.updated_at,
                "image_data": image_data
            }
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error retrieving screenshot metadata: {str(e)}"
            )
    else:
        # screenshot_id实际上就是fragment_id，直接调用现有的函数
        return get_fragment_image(screenshot_id, include_metadata=False, include_image_data=True, db=db)