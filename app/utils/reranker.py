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

        # 为每个结果计算重排序分数
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

        # 按重排序分数降序排序
        return sorted(results, key=lambda x: x["rerank_score"], reverse=True)