from typing import List, Dict, Any
from collections import Counter
import json

class TagRecommender:
    """标签推荐器"""
    
    def generate_recommendations(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """生成推荐标签"""
        if not results:
            return []
        
        # 统计所有标签的频数
        all_tags = []
        for result in results:
            chunk_tags = result.get("tags", [])
            if isinstance(chunk_tags, str):
                try:
                    chunk_tags = json.loads(chunk_tags)
                except:
                    chunk_tags = []
            all_tags.extend(chunk_tags)
        
        tag_freq = Counter(all_tags)
        n_results = len(results)
        
        # 计算每个标签的信息增益分数
        recommendations = []
        for tag, freq in tag_freq.items():
            # EIG Score = abs(freq - (N_reranked / 2))
            eig_score = abs(freq - (n_results / 2))
            recommendations.append({
                "tag": tag,
                "freq": freq,
                "eig_score": eig_score
            })
        
        # 按EIG Score升序，freq降序排序
        recommendations.sort(key=lambda x: (x["eig_score"], -x["freq"]))
        
        return recommendations[:10]  # 返回前10个推荐标签