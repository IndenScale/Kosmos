from sqlalchemy.orm import Session
from ..repositories.chunk_repo import ChunkRepository
from ..repositories.milvus_repo import MilvusRepository
from ..utils.ai_utils import AIUtils
from ..utils.query_parser import QueryParser
from ..utils.reranker import Reranker
from ..utils.recommender import TagRecommender
from ..utils.deduplicator import Deduplicator
from typing import List, Dict, Any, Optional
from app.models.chunk import Chunk
from app.services.screenshot_service import ScreenshotService
from app.config import get_logger
import json

logger = get_logger(__name__)

class SearchService:
    """搜索服务"""

    def __init__(self, db: Session):
        self.db = db
        self.chunk_repo = ChunkRepository(db)
        self.milvus_repo = MilvusRepository()
        self.ai_utils = AIUtils()
        self.query_parser = QueryParser()
        self.reranker = Reranker()
        self.recommender = TagRecommender()
        self.deduplicator = Deduplicator()

    def get_chunk_by_id(self, chunk_id: str) -> Optional[Chunk]:
        """根据ID检索chunk"""
        return self.chunk_repo.get_chunk_by_id(chunk_id)

    def search(self, kb_id: str, query: str, top_k: int = 10) -> Dict[str, Any]:
        """执行语义搜索"""
        logger.info(f"开始搜索，知识库ID: {kb_id}, 查询: {query[:100]}..., top_k: {top_k}")
        
        # 1. 解析查询
        parsed_query = self.query_parser.parse(query)

        # 2. 生成查询向量
        query_vector = self.ai_utils.get_embedding(parsed_query.text)

        # 3. 向量召回和过滤
        milvus_results = self.milvus_repo.retrieve_with_filter(
            kb_id=kb_id,
            query_vector=query_vector,
            must_tags=parsed_query.must_tags,
            must_not_tags=parsed_query.must_not_tags,
            top_k=top_k * 3  # 召回更多结果用于重排序和去重
        )

        # 4. 重排序
        reranked_results = self.reranker.rerank(milvus_results, parsed_query.like_tags)

        # 5. 获取chunk详细信息
        chunk_ids = [r["chunk_id"] for r in reranked_results[:top_k * 2]]  # 获取更多用于去重
        chunks = {}
        for chunk_id in chunk_ids:
            chunk = self.chunk_repo.get_chunk_by_id(chunk_id)
            if chunk:
                chunks[chunk_id] = chunk

        # 6. 构建初步结果，包含截图信息
        screenshot_service = ScreenshotService(self.db)
        initial_results = []
        for result in reranked_results[:top_k * 2]:
            chunk_id = result["chunk_id"]
            if chunk_id in chunks:
                chunk = chunks[chunk_id]
                chunk_tags = json.loads(chunk.tags) if chunk.tags else []
                
                # 获取chunk关联的截图ID
                screenshot_ids = []
                if chunk.page_screenshot_ids:
                    try:
                        parsed_ids = json.loads(chunk.page_screenshot_ids)
                        # 确保screenshot_ids是列表，并过滤掉None值
                        if isinstance(parsed_ids, list):
                            screenshot_ids = [sid for sid in parsed_ids if sid is not None and isinstance(sid, str)]
                        else:
                            screenshot_ids = []
                    except json.JSONDecodeError:
                        logger.warning(f"解析chunk {chunk_id} 的截图ID列表失败")
                        screenshot_ids = []
                
                initial_results.append({
                    "chunk_id": chunk_id,
                    "document_id": chunk.document_id,
                    "content": chunk.content,
                    "tags": chunk_tags,
                    "score": result.get("rerank_score", result["score"]),
                    "screenshot_ids": screenshot_ids  # 添加截图ID列表
                })

        # 7. 去重处理
        deduplicated_results = self.deduplicator.deduplicate_results(initial_results)
        
        # 8. 截取最终结果
        final_results = deduplicated_results[:top_k]
        
        logger.info(f"搜索完成，原始结果: {len(initial_results)}, 去重后: {len(deduplicated_results)}, 最终返回: {len(final_results)}")

        # 9. 生成推荐标签
        recommended_tags = self.recommender.generate_recommendations(reranked_results)

        return {
            "results": final_results,
            "recommended_tags": recommended_tags,
            "stats": {
                "original_count": len(initial_results),
                "deduplicated_count": len(deduplicated_results),
                "final_count": len(final_results)
            }
        }