# app/models/__init__.py
"""
Kosmos 应用的数据库模型模块。
此文件统一导出了所有数据库模型，方便其他模块导入。
"""

# 从 chunk.py 导入
from .chunk import Chunk, IngestionJob

# 从 document.py 导入
from .document import PhysicalFile, Document, KBDocument

# 从 fragment.py 导入 (新增)
from .fragment import Fragment, KBFragment

# 从 index.py 导入 (新增)
from .index import Index

# 从 knowledge_base.py 导入
from .knowledge_base import KBRole, JSONEncodedDict, KnowledgeBase, KBMember

# 从 page_screenshot.py 导入
from .page_screenshot import PageScreenshot

# 从 sdtm.py 导入
from .sdtm import (
    SDTMMode,
    QualityMetrics,
    ProgressMetrics,
    DocumentInfo,
    AbnormalDocument,
    EditOperation,
    DocumentAnnotation,
    SDTMEngineResponse,
    SDTMStats,
    SDTMProcessRequest,
    SDTMJob
)

# 从 user.py 导入
from .user import User

# 为了方便，也可以在这里定义一个包含所有模型的列表
all_models = [
    Chunk,
    IngestionJob,
    PhysicalFile,
    Document,
    KBDocument,
    Fragment,      # 新增
    KBFragment,    # 新增
    Index,         # 新增
    KnowledgeBase,
    KBMember,
    PageScreenshot,
    SDTMJob,
    User
]

# 定义 __all__ 以支持 from app.models import * 语法
__all__ = [
    "Chunk",
    "IngestionJob",
    "PhysicalFile",
    "Document",
    "KBDocument",
    "Fragment",        # 新增
    "KBFragment",      # 新增
    "Index",           # 新增
    "KBRole",
    "JSONEncodedDict",
    "KnowledgeBase",
    "KBMember",
    "PageScreenshot",
    "SDTMMode",
    "QualityMetrics",
    "ProgressMetrics",
    "DocumentInfo",
    "AbnormalDocument",
    "EditOperation",
    "DocumentAnnotation",
    "SDTMEngineResponse",
    "SDTMStats",
    "SDTMProcessRequest",
    "SDTMJob",
    "User",
    "all_models"
]