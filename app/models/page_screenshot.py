from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, LargeBinary
from sqlalchemy.sql import func
from app.db.database import Base
import uuid

class PageScreenshot(Base):
    """页面截图表"""
    __tablename__ = "page_screenshots"
    __table_args__ = {'extend_existing': True}
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    page_number = Column(Integer, nullable=False)  # 页码，从1开始
    file_path = Column(String, nullable=False)  # 截图文件存储路径
    width = Column(Integer, nullable=True)  # 截图宽度
    height = Column(Integer, nullable=True)  # 截图高度
    created_at = Column(DateTime, default=func.now()) 