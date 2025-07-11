from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from app.db.database import get_db
from app.services.screenshot_service import ScreenshotService
from app.dependencies.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/screenshots", tags=["screenshots"])

@router.get("/{screenshot_id}/info")
async def get_screenshot_info(
    screenshot_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """获取截图信息（不包含文件内容）"""
    
    screenshot_service = ScreenshotService(db)
    info = screenshot_service.get_screenshot_info(screenshot_id)
    
    if not info:
        raise HTTPException(status_code=404, detail="截图不存在")
    
    return {
        "success": True,
        "data": info
    }

@router.get("/{screenshot_id}/image")
async def get_screenshot_image(
    screenshot_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取截图图片文件"""
    
    screenshot_service = ScreenshotService(db)
    
    # 获取截图信息
    screenshot = screenshot_service.get_screenshot_by_id(screenshot_id)
    if not screenshot:
        raise HTTPException(status_code=404, detail="截图不存在")
    
    # 获取文件内容
    content = screenshot_service.get_screenshot_file_content(screenshot_id)
    if not content:
        raise HTTPException(status_code=404, detail="截图文件不存在")
    
    # 返回图片响应
    return Response(
        content=content,
        media_type="image/png",
        headers={
            "Content-Disposition": f"inline; filename=page_{screenshot.page_number}.png"
        }
    )

@router.get("/document/{document_id}")
async def get_document_screenshots(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """获取文档的所有页面截图信息"""
    
    screenshot_service = ScreenshotService(db)
    screenshots = screenshot_service.get_screenshots_by_document(document_id)
    
    # 转换为响应格式
    screenshot_list = []
    for screenshot in screenshots:
        screenshot_info = {
            "id": screenshot.id,
            "page_number": screenshot.page_number,
            "width": screenshot.width,
            "height": screenshot.height,
            "created_at": screenshot.created_at.isoformat() if screenshot.created_at is not None else None
        }
        screenshot_list.append(screenshot_info)
    
    return {
        "success": True,
        "data": {
            "document_id": document_id,
            "total_pages": len(screenshot_list),
            "screenshots": screenshot_list
        }
    }

@router.post("/batch")
async def get_screenshots_batch(
    screenshot_ids: List[str],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """批量获取截图信息"""
    
    screenshot_service = ScreenshotService(db)
    screenshots = screenshot_service.get_screenshots_by_ids(screenshot_ids)
    
    # 转换为响应格式
    screenshot_list = []
    for screenshot in screenshots:
        screenshot_info = {
            "id": screenshot.id,
            "document_id": screenshot.document_id,
            "page_number": screenshot.page_number,
            "width": screenshot.width,
            "height": screenshot.height,
            "created_at": screenshot.created_at.isoformat() if screenshot.created_at is not None else None
        }
        screenshot_list.append(screenshot_info)
    
    return {
        "success": True,
        "data": {
            "requested_count": len(screenshot_ids),
            "found_count": len(screenshot_list),
            "screenshots": screenshot_list
        }
    } 