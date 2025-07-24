# app/services/__init__.py
"""
Kosmos 应用的服务层模块。
此文件统一导出了所有服务类，方便其他模块导入。
"""

# 从 document_service.py 导入
from .document_service import DocumentService

# 从 ingestion_service.py 导入
from .ingestion_service import IngestionService

# 从 kb_service.py 导入
from .kb_service import KBService

# 从 screenshot_service.py 导入
from .screenshot_service import ScreenshotService

# 从 sdtm_engine.py 导入
from .sdtm_engine import SDTMEngine

# 从 sdtm_service.py 导入
from .sdtm_service import SDTMService

# 从 sdtm_stats_service.py 导入
from .sdtm_stats_service import SDTMStatsService

# 从 search_service.py 导入
from .search_service import SearchService

# 从 tagging_service.py 导入
from .tagging_service import TaggingService

# 从 user_service.py 导入
from .user_service import UserService

# 为了方便，也可以在这里定义一个包含所有服务的列表
all_services = [
    DocumentService,
    IngestionService,
    KBService,
    ScreenshotService,
    SDTMEngine,
    SDTMService,
    SDTMStatsService,
    SearchService,
    TaggingService,
    UserService
]

# 定义 __all__ 以支持 from app.services import * 语法
__all__ = [
    "DocumentService",
    "IngestionService",
    "KBService",
    "ScreenshotService",
    "SDTMEngine",
    "SDTMService",
    "SDTMStatsService",
    "SearchService",
    "TaggingService",
    "UserService",
    "all_services"
]