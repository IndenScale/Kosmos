# backend/app/tasks/__init__.py
"""
This package contains all the Dramatiq actor definitions for background tasks.
"""
print("--- [Tasks Probe] tasks/__init__.py loaded ---")
# 1. 关键修复：首先导入并配置 Broker。
#    这确保了在加载任何 actor 模块（以及它们的 @dramatiq.actor 装饰器）之前，
#    全局的 broker 实例已经被正确设置为 Redis Broker。
print("--- [Tasks Probe] Importing broker...")
# [FIX] Import the broker object directly into the package's namespace.
from .broker import broker
print("--- [Tasks Probe] Broker imported. Importing actors...")

# 2. 现在，导入所有 actors。
#    这会将它们注册到已配置的 broker，并使它们可以通过 `tasks` 包被外部模块访问。
from .chunking.actor import chunk_document_actor
from .asset_analysis.actor import analyze_asset_actor
from .indexing.actor import indexing_actor
from .content_extraction.actor import content_extraction_actor
print("--- [Tasks Probe] Actors imported.")

