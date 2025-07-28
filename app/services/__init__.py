# app/services/__init__.py
"""
Kosmos 应用的服务层模块。
此文件统一导出了所有服务类，方便其他模块导入。
"""
# 从 user_service.py 导入
from .user_service import UserService

# # 从 document_service.py 导入
# from .document_service import DocumentService

# # 从 ingestion_service.py 导入
# from .ingestion_service import IngestionService

# # 从 kb_service.py 导入
# from .kb_service import KBService


# # 从 search_service.py 导入
# from .search_service import SearchService




# 为了方便，也可以在这里定义一个包含所有服务的列表
all_services = [
    UserService
    # DocumentService,
    # IngestionService,
    # KBService,
    # SearchService,
    # TaggingService,
]

# 定义 __all__ 以支持 from app.services import * 语法
__all__ = [
    "all_services",
    "UserService"
    # "DocumentService",
    # "IngestionService",
    # "KBService",
    # "SearchService",
    # "TaggingService",
    # "UserService",
    #
]