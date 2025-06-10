from sqlalchemy.orm import Session
from repositories.chunk_repo import ChunkRepository
from repositories.milvus_repo import MilvusRepository
from utils.ai_utils import AIUtils
from utils.query_parser import QueryParser
from utils.reranker import Reranker
from utils.recommender import TagRecommender
from typing import List, Dict, Any, Optional
from app.models.chunk import Chunk
import json

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

    def get_chunk_by_id(self, chunk_id: str) -> Optional[Chunk]:
        """根据ID检索chunk"""
        return self.chunk_repo.get_chunk_by_id(chunk_id)

    def search(self, kb_id: str, query: str, top_k: int = 10) -> Dict[str, Any]:
        """执行语义搜索"""
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
            top_k=top_k * 2  # 召回更多结果用于重排序
        )

        # 4. 重排序
        reranked_results = self.reranker.rerank(milvus_results, parsed_query.like_tags)

        # 5. 获取chunk详细信息
        chunk_ids = [r["chunk_id"] for r in reranked_results[:top_k]]
        chunks = {}
        for chunk_id in chunk_ids:
            chunk = self.chunk_repo.get_chunk_by_id(chunk_id)
            if chunk:
                chunks[chunk_id] = chunk

        # 6. 构建最终结果
        final_results = []
        for result in reranked_results[:top_k]:
            chunk_id = result["chunk_id"]
            if chunk_id in chunks:
                chunk = chunks[chunk_id]
                chunk_tags = json.loads(chunk.tags) if chunk.tags else []
                final_results.append({
                    "chunk_id": chunk_id,
                    "document_id": chunk.document_id,
                    "content": chunk.content,
                    "tags": chunk_tags,
                    "score": result.get("rerank_score", result["score"])
                })

        # 7. 生成推荐标签
        recommended_tags = self.recommender.generate_recommendations(reranked_results)

        return {
            "results": final_results,
            "recommended_tags": recommended_tags
        }