# app/repositories/__init__.py
"""
Kosmos 应用的数据访问层模块。
此文件统一导出了所有数据访问仓库，方便其他模块导入。
"""

# 从 chunk_repo.py 导入
from .chunk_repo import ChunkRepository

# 从 document_repo.py 导入
from .document_repo import DocumentService, DocumentRepository

# 从 milvus_repo.py 导入
from .milvus_repo import MilvusRepository

# 为了方便，也可以在这里定义一个包含所有仓库的列表
all_repositories = [
    ChunkRepository,
    DocumentService,
    DocumentRepository,
    MilvusRepository
]

# 定义 __all__ 以支持 from app.repositories import * 语法
__all__ = [
    "ChunkRepository",
    "DocumentService",
    "DocumentRepository",
    "MilvusRepository",
    "all_repositories"
]