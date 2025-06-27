from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pathlib import Path
import os
import uuid

from app.models.page_screenshot import PageScreenshot
from app.models.chunk import Chunk
from app.config import get_logger

class ScreenshotService:
    """页面截图服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.logger = get_logger(self.__class__.__name__)
    
    def save_screenshots(self, screenshots: List[PageScreenshot]) -> List[str]:
        """保存页面截图记录到数据库
        
        Args:
            screenshots: 页面截图列表
            
        Returns:
            List[str]: 保存的截图ID列表
        """
        try:
            screenshot_ids = []
            
            for screenshot in screenshots:
                self.db.add(screenshot)
                # 由于我们在创建时已经设置了ID，可以直接使用
                screenshot_ids.append(screenshot.id)
            
            self.db.commit()
            
            self.logger.info(f"保存了{len(screenshots)}个页面截图记录")
            return screenshot_ids
            
        except Exception as e:
            self.db.rollback()
            self.logger.error(f"保存页面截图失败: {str(e)}")
            raise Exception(f"保存页面截图失败: {str(e)}")
    
    def get_screenshot_by_id(self, screenshot_id: str) -> Optional[PageScreenshot]:
        """根据ID获取页面截图
        
        Args:
            screenshot_id: 截图ID
            
        Returns:
            Optional[PageScreenshot]: 页面截图记录，如果不存在则返回None
        """
        try:
            screenshot = self.db.query(PageScreenshot).filter(
                PageScreenshot.id == screenshot_id
            ).first()
            
            return screenshot
            
        except Exception as e:
            self.logger.error(f"获取页面截图失败: {screenshot_id}, 错误: {str(e)}")
            return None
    
    def get_screenshots_by_document(self, document_id: str) -> List[PageScreenshot]:
        """获取文档的所有页面截图
        
        Args:
            document_id: 文档ID
            
        Returns:
            List[PageScreenshot]: 页面截图列表
        """
        try:
            screenshots = self.db.query(PageScreenshot).filter(
                PageScreenshot.document_id == document_id
            ).order_by(PageScreenshot.page_number).all()
            
            return screenshots
            
        except Exception as e:
            self.logger.error(f"获取文档页面截图失败: {document_id}, 错误: {str(e)}")
            return []
    
    def get_screenshots_by_ids(self, screenshot_ids: List[str]) -> List[PageScreenshot]:
        """根据ID列表批量获取页面截图
        
        Args:
            screenshot_ids: 截图ID列表
            
        Returns:
            List[PageScreenshot]: 页面截图列表
        """
        try:
            if not screenshot_ids:
                return []
            
            screenshots = self.db.query(PageScreenshot).filter(
                PageScreenshot.id.in_(screenshot_ids)
            ).order_by(PageScreenshot.page_number).all()
            
            return screenshots
            
        except Exception as e:
            self.logger.error(f"批量获取页面截图失败: {str(e)}")
            return []
    
    def get_screenshot_file_content(self, screenshot_id: str) -> Optional[bytes]:
        """获取截图文件内容
        
        Args:
            screenshot_id: 截图ID
            
        Returns:
            Optional[bytes]: 截图文件内容，如果不存在则返回None
        """
        try:
            screenshot = self.get_screenshot_by_id(screenshot_id)
            if not screenshot:
                return None
            
            file_path = Path(str(screenshot.file_path))
            if not file_path.exists():
                self.logger.warning(f"截图文件不存在: {file_path}")
                return None
            
            with open(file_path, 'rb') as f:
                content = f.read()
            
            return content
            
        except Exception as e:
            self.logger.error(f"读取截图文件失败: {screenshot_id}, 错误: {str(e)}")
            return None
    
    def delete_screenshots_by_document(self, document_id: str) -> bool:
        """删除文档的所有页面截图
        
        Args:
            document_id: 文档ID
            
        Returns:
            bool: 是否删除成功
        """
        try:
            # 获取要删除的截图记录
            screenshots = self.get_screenshots_by_document(document_id)
            
            # 删除截图文件
            for screenshot in screenshots:
                try:
                    file_path = Path(str(screenshot.file_path))
                    if file_path.exists():
                        os.remove(file_path)
                        self.logger.info(f"删除截图文件: {file_path}")
                except Exception as e:
                    self.logger.warning(f"删除截图文件失败: {file_path}, 错误: {str(e)}")
            
            # 删除数据库记录
            self.db.query(PageScreenshot).filter(
                PageScreenshot.document_id == document_id
            ).delete()
            
            self.db.commit()
            
            self.logger.info(f"删除文档页面截图: {document_id}, 共{len(screenshots)}个")
            return True
            
        except Exception as e:
            self.db.rollback()
            self.logger.error(f"删除文档页面截图失败: {document_id}, 错误: {str(e)}")
            return False
    
    def get_screenshot_info(self, screenshot_id: str) -> Optional[Dict[str, Any]]:
        """获取截图信息（不包含文件内容）
        
        Args:
            screenshot_id: 截图ID
            
        Returns:
            Optional[Dict[str, Any]]: 截图信息字典
        """
        try:
            screenshot = self.get_screenshot_by_id(screenshot_id)
            if not screenshot:
                return None
            
            info = {
                "id": screenshot.id,
                "document_id": screenshot.document_id,
                "page_number": screenshot.page_number,
                "width": screenshot.width,
                "height": screenshot.height,
                "created_at": screenshot.created_at.isoformat() if screenshot.created_at is not None else None,
                "file_exists": Path(str(screenshot.file_path)).exists()
            }
            
            return info
            
        except Exception as e:
            self.logger.error(f"获取截图信息失败: {screenshot_id}, 错误: {str(e)}")
            return None 