from typing import List, Dict, Any, Optional
from collections import Counter
import json
import logging
from sqlalchemy.orm import Session

from app.schemas.search import RecommendedTag

logger = logging.getLogger(__name__)


class TagRecommendationService:
    """标签推荐服务
    
    基于 ITD (理想标签偏移) 算法实现标签推荐功能。
    ITD = abs(hits - reranker_top_k / 2)
    ITD 越小，说明该标签在结果中分布越"均匀"，既不过于普遍也不过于稀有，
    是区分结果的理想候选。
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def generate_recommendations(
        self, 
        results: List[Dict[str, Any]], 
        tag_suggestion_top_k: int = 10
    ) -> List[RecommendedTag]:
        """生成推荐标签
        
        Args:
            results: 重排后的搜索结果列表
            tag_suggestion_top_k: 返回的推荐标签数量
            
        Returns:
            推荐标签列表，按ITD分数升序排列
        """
        if not results:
            return []
        
        try:
            # 统计所有标签的出现次数
            all_tags = []
            for result in results:
                tags = self._extract_tags(result)
                all_tags.extend(tags)
            
            if not all_tags:
                logger.info("搜索结果中没有找到任何标签")
                return []
            
            tag_freq = Counter(all_tags)
            reranker_top_k = len(results)
            
            # 计算每个标签的ITD (理想标签偏移)
            recommendations = []
            for tag, hits in tag_freq.items():
                # ITD = abs(hits - reranker_top_k / 2)
                itd_score = abs(hits - (reranker_top_k / 2))
                
                # 计算相关性分数 (ITD越小相关性越高)
                # 使用归一化的相关性分数，范围 [0, 1]
                max_possible_itd = max(reranker_top_k / 2, reranker_top_k - reranker_top_k / 2)
                relevance = 1.0 - (itd_score / max_possible_itd) if max_possible_itd > 0 else 1.0
                
                recommendations.append(RecommendedTag(
                    tag=tag,
                    count=hits,
                    relevance=round(relevance, 4)
                ))
            
            # 按ITD分数升序排序（ITD越小越好），然后按出现次数降序排序
            recommendations.sort(key=lambda x: (-x.relevance, -x.count))
            
            # 返回前 tag_suggestion_top_k 个推荐标签
            result_recommendations = recommendations[:tag_suggestion_top_k]
            
            logger.info(f"生成了 {len(result_recommendations)} 个推荐标签")
            return result_recommendations
            
        except Exception as e:
            logger.error(f"生成推荐标签失败: {str(e)}")
            return []
    
    def _extract_tags(self, result: Dict[str, Any]) -> List[str]:
        """从搜索结果中提取标签
        
        Args:
            result: 搜索结果项
            
        Returns:
            标签列表
        """
        tags = result.get("tags", [])
        
        # 处理不同的标签格式
        if isinstance(tags, str):
            try:
                # 尝试解析JSON字符串
                tags = json.loads(tags)
            except (json.JSONDecodeError, TypeError):
                # 如果不是JSON，尝试按逗号分割
                tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
        
        # 确保返回字符串列表
        if isinstance(tags, list):
            return [str(tag).strip() for tag in tags if tag and str(tag).strip()]
        
        return []
    
    def get_tag_statistics(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """获取标签统计信息
        
        Args:
            results: 搜索结果列表
            
        Returns:
            标签统计信息
        """
        if not results:
            return {
                "total_tags": 0,
                "unique_tags": 0,
                "tag_distribution": {},
                "coverage": 0.0
            }
        
        try:
            all_tags = []
            results_with_tags = 0
            
            for result in results:
                tags = self._extract_tags(result)
                if tags:
                    all_tags.extend(tags)
                    results_with_tags += 1
            
            tag_freq = Counter(all_tags)
            coverage = results_with_tags / len(results) if results else 0.0
            
            return {
                "total_tags": len(all_tags),
                "unique_tags": len(tag_freq),
                "tag_distribution": dict(tag_freq.most_common(20)),  # 前20个最常见标签
                "coverage": round(coverage, 4),
                "results_count": len(results),
                "results_with_tags": results_with_tags
            }
            
        except Exception as e:
            logger.error(f"获取标签统计信息失败: {str(e)}")
            return {
                "total_tags": 0,
                "unique_tags": 0,
                "tag_distribution": {},
                "coverage": 0.0,
                "error": str(e)
            }