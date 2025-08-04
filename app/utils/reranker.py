from typing import List, Dict, Any
import json

class Reranker:
    """搜索结果重排序器"""

    def __init__(self, like_tag_weight: float = 1.0):
        self.like_tag_weight = like_tag_weight

    def rerank(self, results: List[Dict[str, Any]], like_tags: List[str]) -> List[Dict[str, Any]]:
        """根据like_tags对结果进行重排序"""
        if not like_tags:
            return results

        for result in results:
            chunk_tags = result.get("tags", [])
            if isinstance(chunk_tags, str):
                try:
                    chunk_tags = json.loads(chunk_tags)
                except:
                    chunk_tags = []

            # 计算匹配的like_tags数量
            matched_like_tags = sum(1 for tag in like_tags if tag in chunk_tags)

            # 重排序分数 = 原始分数 + (匹配标签数 * 权重)
            result["rerank_score"] = result["score"] + (matched_like_tags * self.like_tag_weight)
            
            # 如果有匹配的like_tags，设置booster_score（只加标签匹配分数）
            if matched_like_tags > 0:
                result["booster_score"] = result["score"] + (matched_like_tags * self.like_tag_weight)

        # 按booster_score或rerank_score降序排序
        sorted_results = sorted(results, key=lambda x: x.get("booster_score", x.get("rerank_score", x["score"])), reverse=True)
        return sorted_results