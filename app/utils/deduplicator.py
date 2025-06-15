import hashlib
import numpy as np
from typing import List, Dict, Any, Set
from app.config import config
from app.utils.ai_utils import AIUtils
import logging

logger = logging.getLogger(__name__)

class Deduplicator:
    """去重工具类"""

    def __init__(self):
        self.ai_utils = AIUtils() if config.deduplication.semantic_similarity_enabled else None
        self.config = config.deduplication

    def deduplicate_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """对搜索结果进行去重"""
        if not self.config.enabled or not results:
            return results

        logger.info(f"开始去重，原始结果数量: {len(results)}")

        # 1. 字面值去重
        if self.config.literal_match_enabled:
            results = self._literal_deduplication(results)
            logger.info(f"字面值去重后数量: {len(results)}")

        # 2. 语义相似度去重
        if self.config.semantic_similarity_enabled and len(results) > 1:
            results = self._semantic_deduplication_by_score(results)
            logger.info(f"语义去重后数量: {len(results)}")

        return results

    def _literal_deduplication(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """字面值去重 - 基于内容哈希"""
        seen_hashes: Set[str] = set()
        deduplicated = []

        for result in results:
            content = result.get('content', '').strip()

            # 跳过过短的内容
            if len(content) < self.config.min_content_length:
                deduplicated.append(result)
                continue

            # 计算内容哈希
            content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()

            if content_hash not in seen_hashes:
                seen_hashes.add(content_hash)
                deduplicated.append(result)
            else:
                logger.debug(f"发现重复内容，已跳过: {content[:50]}...")

        return deduplicated

    def _semantic_deduplication_by_score(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """基于搜索结果相似度分数的语义去重"""
        if not results:
            return results

        # 按相似度分数降序排序，确保保留最相关的结果
        sorted_results = sorted(results, key=lambda x: x.get('score', 0), reverse=True)

        deduplicated = []

        for current_result in sorted_results:
            current_score = current_result.get('score', 0)
            current_content = current_result.get('content', '').strip()

            # 跳过过短的内容
            if len(current_content) < self.config.min_content_length:
                deduplicated.append(current_result)
                continue

            # 检查与已保留结果的相似度
            is_duplicate = False

            for existing_result in deduplicated:
                existing_score = existing_result.get('score', 0)
                existing_content = existing_result.get('content', '').strip()

                if len(existing_content) < self.config.min_content_length:
                    continue

                # 计算相似度阈值：与查询的相似度相等或在0.5%以内
                # 如果两个结果的分数差异在0.5%以内，认为它们语义相似
                score_diff_threshold = 0.005  # 0.5%

                # 计算分数差异的相对比例
                if existing_score > 0:
                    relative_diff = abs(current_score - existing_score) / existing_score
                else:
                    relative_diff = abs(current_score - existing_score)

                if relative_diff <= score_diff_threshold:
                    # 进一步检查内容相似性（简单的字符串相似度检查）
                    content_similarity = self._simple_content_similarity(current_content, existing_content)

                    if content_similarity > 0.95:  # 80%的内容相似度
                        logger.debug(f"发现语义相似内容 (分数差异: {relative_diff:.3f}, 内容相似度: {content_similarity:.3f})，已跳过: {current_content[:50]}...")
                        is_duplicate = True
                        break

            if not is_duplicate:
                deduplicated.append(current_result)

        return deduplicated

    def _simple_content_similarity(self, content1: str, content2: str) -> float:
        """简单的内容相似度计算（基于字符级别的相似性）"""
        try:
            # 使用最长公共子序列的思想计算相似度
            len1, len2 = len(content1), len(content2)
            if len1 == 0 and len2 == 0:
                return 1.0
            if len1 == 0 or len2 == 0:
                return 0.0

            # 简化版本：计算字符级别的重叠度
            set1 = set(content1.lower())
            set2 = set(content2.lower())

            intersection = len(set1.intersection(set2))
            union = len(set1.union(set2))

            if union == 0:
                return 0.0

            return intersection / union
        except Exception as e:
            logger.warning(f"计算内容相似度失败: {e}")
            return 0.0

    # 保留原有的语义去重方法作为备用
    def _semantic_deduplication(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """语义相似度去重（原有方法，基于embedding计算）"""
        if not self.ai_utils:
            return results

        deduplicated = []
        embeddings_cache = {}

        for i, result in enumerate(results):
            content = result.get('content', '').strip()

            # 跳过过短的内容
            if len(content) < self.config.min_content_length:
                deduplicated.append(result)
                continue

            # 获取当前内容的embedding
            try:
                if content not in embeddings_cache:
                    embeddings_cache[content] = self.ai_utils.get_embedding(content)
                current_embedding = embeddings_cache[content]
            except Exception as e:
                logger.warning(f"获取embedding失败，跳过语义去重: {e}")
                deduplicated.append(result)
                continue

            # 检查与已有结果的相似度
            is_duplicate = False
            for existing_result in deduplicated:
                existing_content = existing_result.get('content', '').strip()

                if len(existing_content) < self.config.min_content_length:
                    continue

                try:
                    if existing_content not in embeddings_cache:
                        embeddings_cache[existing_content] = self.ai_utils.get_embedding(existing_content)
                    existing_embedding = embeddings_cache[existing_content]

                    # 计算余弦相似度
                    similarity = self._cosine_similarity(current_embedding, existing_embedding)

                    if similarity > self.config.semantic_similarity_threshold:
                        logger.debug(f"发现语义相似内容 (相似度: {similarity:.3f})，已跳过: {content[:50]}...")
                        is_duplicate = True
                        break

                except Exception as e:
                    logger.warning(f"计算语义相似度失败: {e}")
                    continue

            if not is_duplicate:
                deduplicated.append(result)

        return deduplicated

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算两个向量的余弦相似度"""
        try:
            vec1_np = np.array(vec1)
            vec2_np = np.array(vec2)

            # 计算余弦相似度
            dot_product = np.dot(vec1_np, vec2_np)
            norm1 = np.linalg.norm(vec1_np)
            norm2 = np.linalg.norm(vec2_np)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            return dot_product / (norm1 * norm2)
        except Exception as e:
            logger.warning(f"计算余弦相似度失败: {e}")
            return 0.0