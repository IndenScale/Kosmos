from sqlalchemy.orm import Session
from typing import Dict, List, Optional, Tuple, Any
import json
import logging
from collections import defaultdict, Counter
from datetime import datetime

from app.models.chunk import Chunk
from app.models.knowledge_base import KnowledgeBase
from app.models.sdtm import (
    QualityMetrics, ProgressMetrics, AbnormalDocument, 
    DocumentInfo, SDTMStats
)
from app.repositories.chunk_repo import ChunkRepository

# 配置日志
logger = logging.getLogger(__name__)

class SDTMStatsService:
    """SDTM统计服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.chunk_repo = ChunkRepository(db)
    
    def get_kb_sdtm_stats(self, kb_id: str) -> SDTMStats:
        """获取知识库的SDTM统计信息，支持冷启动"""
        from fastapi import HTTPException, status
        
        kb = self.db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
        if not kb:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Knowledge base {kb_id} not found"
            )
        
        # 获取所有chunks（可能为空）
        chunks = self.chunk_repo.get_chunks_by_kb(kb_id)
        
        # 检查是否为冷启动情况
        cold_start_info = self._check_cold_start_status(kb_id, chunks)
        
        # 即使没有chunks也要返回有意义的统计信息
        try:
            # 计算质量指标
            quality_metrics = self._calculate_quality_metrics(chunks)
            
            # 计算进度指标（包含冷启动信息）
            progress_metrics = self._calculate_progress_metrics(kb, chunks, cold_start_info)
            
            # 获取异常文档
            abnormal_documents = self._get_abnormal_documents(chunks, quality_metrics)
            
            # 如果是冷启动情况，添加冷启动建议
            if cold_start_info['is_cold_start']:
                abnormal_documents.extend(self._get_cold_start_recommendations(cold_start_info))
            
            return SDTMStats(
                progress_metrics=progress_metrics,
                quality_metrics=quality_metrics,
                abnormal_documents=abnormal_documents,
                last_updated=datetime.now()
            )
        except Exception as e:
            # 如果计算出错，返回默认的空统计信息
            logger.warning(f"Failed to calculate SDTM stats, returning defaults: {e}")
            return self._get_default_stats(kb_id, kb)
    
    def _calculate_quality_metrics(self, chunks: List[Chunk]) -> QualityMetrics:
        """计算质量指标"""
        tags_document_distribution = defaultdict(int)
        documents_tag_distribution = defaultdict(int)
        
        # 解析每个chunk的标签
        chunk_tags_map = {}
        all_tags = set()
        
        for chunk in chunks:
            try:
                if chunk.tags:
                    if isinstance(chunk.tags, str):
                        tags = json.loads(chunk.tags)
                    else:
                        tags = chunk.tags
                    
                    if isinstance(tags, list):
                        chunk_tags_map[chunk.id] = tags
                        tags_document_distribution[len(tags)] += 1
                        
                        for tag in tags:
                            all_tags.add(tag)
                            documents_tag_distribution[tag] += 1
                else:
                    chunk_tags_map[chunk.id] = []
                    tags_document_distribution[0] += 1
            except (json.JSONDecodeError, TypeError):
                chunk_tags_map[chunk.id] = []
                tags_document_distribution[0] += 1
        
        # 计算异常文档数量
        tag_counts = list(tags_document_distribution.keys())
        tag_usage_counts = list(documents_tag_distribution.values())
        
        # 定义阈值
        min_tags_per_doc = 1
        max_tags_per_doc = 10
        min_usage_per_tag = 1
        max_usage_per_tag = 50
        
        under_annotated_docs_count = sum(
            count for tag_count, count in tags_document_distribution.items() 
            if tag_count < min_tags_per_doc
        )
        
        over_annotated_docs_count = sum(
            count for tag_count, count in tags_document_distribution.items() 
            if tag_count > max_tags_per_doc
        )
        
        under_used_tags_count = sum(
            1 for usage in tag_usage_counts 
            if usage < min_usage_per_tag
        )
        
        over_used_tags_count = sum(
            1 for usage in tag_usage_counts 
            if usage > max_usage_per_tag
        )
        
        # 计算无法区分的文档（具有完全相同标签的文档）
        tag_combinations = defaultdict(list)
        for chunk_id, tags in chunk_tags_map.items():
            tag_combo = tuple(sorted(tags))
            tag_combinations[tag_combo].append(chunk_id)
        
        indistinguishable_docs_count = sum(
            len(chunks) for chunks in tag_combinations.values() 
            if len(chunks) > 1
        )
        
        return QualityMetrics(
            tags_document_distribution={str(k): v for k, v in tags_document_distribution.items()},
            documents_tag_distribution={str(k): v for k, v in documents_tag_distribution.items()},
            under_annotated_docs_count=under_annotated_docs_count,
            over_annotated_docs_count=over_annotated_docs_count,
            under_used_tags_count=under_used_tags_count,
            over_used_tags_count=over_used_tags_count,
            indistinguishable_docs_count=indistinguishable_docs_count
        )
    
    def _calculate_progress_metrics(self, kb: KnowledgeBase, chunks: List[Chunk], cold_start_info: Dict[str, Any] = None) -> ProgressMetrics:
        """计算进度指标，支持冷启动"""
        # 计算标签字典大小
        tag_dict_size = self._count_tags_in_dictionary(kb.tag_dictionary)
        
        # 估算迭代次数（基于chunks数量或文档数量）
        total_chunks = len(chunks)
        
        # 冷启动情况的特殊处理
        if cold_start_info and cold_start_info.get('is_cold_start', False):
            cold_start_type = cold_start_info.get('cold_start_type')
            total_documents = cold_start_info.get('total_documents', 0)
            
            if cold_start_type == "no_documents":
                # 完全空的知识库
                return ProgressMetrics(
                    current_iteration=0,
                    total_iterations=1,
                    current_tags_dictionary_size=tag_dict_size,
                    max_tags_dictionary_size=1000
                )
            
            elif cold_start_type == "documents_no_chunks":
                # 有文档但没有chunks - 可以进行冷启动
                estimated_iterations = max(1, total_documents // 5)  # 每5个文档一次迭代
                return ProgressMetrics(
                    current_iteration=0,  # 冷启动状态
                    total_iterations=estimated_iterations,
                    current_tags_dictionary_size=tag_dict_size,
                    max_tags_dictionary_size=1000
                )
            
            elif cold_start_type == "no_tag_dictionary":
                # 有数据但没有标签字典
                estimated_iterations = max(1, total_chunks // 10)
                return ProgressMetrics(
                    current_iteration=0,  # 需要初始化
                    total_iterations=estimated_iterations,
                    current_tags_dictionary_size=0,  # 强制显示为0
                    max_tags_dictionary_size=1000
                )
        
        # 正常情况的处理
        if total_chunks == 0:
            # 没有chunks时的默认值
            return ProgressMetrics(
                current_iteration=0,
                total_iterations=1,
                current_tags_dictionary_size=tag_dict_size,
                max_tags_dictionary_size=1000
            )
        
        estimated_iterations = max(1, total_chunks // 10)  # 每10个chunk一次迭代
        
        # 当前迭代次数（基于最后更新时间估算）
        current_iteration = 1
        if kb.last_tag_directory_update_time:
            days_since_update = (datetime.now() - kb.last_tag_directory_update_time).days
            current_iteration = min(estimated_iterations, days_since_update + 1)
        
        return ProgressMetrics(
            current_iteration=current_iteration,
            total_iterations=estimated_iterations,
            current_tags_dictionary_size=tag_dict_size,
            max_tags_dictionary_size=1000  # 默认最大值
        )
    
    def _count_tags_in_dictionary(self, tag_dict) -> int:
        """递归计算标签字典中的标签数量"""
        if not tag_dict:
            return 0
        
        # 如果tag_dict是字符串，尝试解析为JSON
        if isinstance(tag_dict, str):
            try:
                import json
                tag_dict = json.loads(tag_dict)
            except (json.JSONDecodeError, TypeError):
                return 0
        
        # 确保tag_dict是字典
        if not isinstance(tag_dict, dict):
            return 0
        
        count = 0
        for key, value in tag_dict.items():
            if isinstance(value, dict):
                count += self._count_tags_in_dictionary(value)
            elif isinstance(value, list):
                count += len(value)
            else:
                count += 1
        return count
    
    def _get_abnormal_documents(self, chunks: List[Chunk], quality_metrics: QualityMetrics) -> List[AbnormalDocument]:
        """获取异常文档列表 - 完整显示所有异常文档，不进行截断"""
        abnormal_docs = []
        
        # 获取标注不足的文档
        for chunk in chunks:
            try:
                if chunk.tags:
                    if isinstance(chunk.tags, str):
                        tags = json.loads(chunk.tags)
                    else:
                        tags = chunk.tags
                    
                    if not isinstance(tags, list):
                        tags = []
                else:
                    tags = []
                
                # 检查标注不足
                if len(tags) < 1:
                    abnormal_docs.append(AbnormalDocument(
                        doc_id=chunk.id,
                        reason="标签数量不足",
                        content=chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content,
                        current_tags=tags,
                        anomaly_type="under_annotated"
                    ))
                
                # 检查标注过度
                elif len(tags) > 10:
                    abnormal_docs.append(AbnormalDocument(
                        doc_id=chunk.id,
                        reason="标签数量过多",
                        content=chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content,
                        current_tags=tags,
                        anomaly_type="over_annotated"
                    ))
                
            except (json.JSONDecodeError, TypeError):
                abnormal_docs.append(AbnormalDocument(
                    doc_id=chunk.id,
                    reason="标签格式错误",
                    content=chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content,
                    current_tags=[],
                    anomaly_type="under_annotated"
                ))
        
        # 检查无法区分的文档 - 优化策略，只选择最有代表性的文档
        tag_combinations = defaultdict(list)
        for chunk in chunks:
            try:
                if chunk.tags:
                    if isinstance(chunk.tags, str):
                        tags = json.loads(chunk.tags)
                    else:
                        tags = chunk.tags
                    
                    if isinstance(tags, list) and len(tags) > 0:  # 只考虑有标签的文档
                        tag_combo = tuple(sorted(tags))
                        tag_combinations[tag_combo].append(chunk)
            except (json.JSONDecodeError, TypeError):
                continue
        
        # 智能选择无法区分的文档
        for tag_combo, chunks_with_same_tags in tag_combinations.items():
            if len(chunks_with_same_tags) > 1:
                # 策略：从每组相同标签的文档中选择最有代表性的
                # 1. 优先选择内容最长的（信息量最大）
                # 2. 如果组内文档超过3个，只选择前3个代表性最强的
                sorted_chunks = sorted(chunks_with_same_tags, key=lambda x: len(x.content), reverse=True)
                max_representatives = min(3, len(sorted_chunks))  # 每组最多3个代表
                
                for i, chunk in enumerate(sorted_chunks[:max_representatives]):
                    priority_score = max_representatives - i  # 优先级分数
                    abnormal_docs.append(AbnormalDocument(
                        doc_id=chunk.id,
                        reason=f"与其他{len(chunks_with_same_tags)-1}个文档具有相同标签（需要细化区分），优先级:{priority_score}",
                        content=chunk.content[:300] + "..." if len(chunk.content) > 300 else chunk.content,  # 增加内容长度
                        current_tags=list(tag_combo),
                        anomaly_type="indistinguishable"
                    ))
        
        return abnormal_docs
    
    def get_documents_to_process(self, kb_id: str, batch_size: int = 10) -> List[DocumentInfo]:
        """获取待处理的文档 - 为SDTM引擎准备文档，限制数量以规避LLM上下文处理能力限制
        
        策略：
        - 总文档数不超过25条（LLM上下文限制）
        - 异常文档（标签错误+标注不足）不超过5条（平衡处理效率）
        - 平衡新信息流的处理，促进符号体系的内聚性
        
        注意：此方法的截断是为了适应SDTM引擎的处理能力，不影响统计展示
        """
        
        # 限制总批次大小，确保不超过25条
        max_batch_size = min(batch_size, 25)
        max_abnormal_docs = 5  # 最大异常文档数
        
        # 首先获取所有chunks
        all_chunks = self.chunk_repo.get_chunks_by_kb(kb_id)
        
        if not all_chunks:
            return []
        
        # 分类chunks - 增加对无法区分文档的特殊处理
        untagged_chunks = []
        under_tagged_chunks = []
        error_tagged_chunks = []
        indistinguishable_chunks = []  # 无法区分的chunks - 最高优先级
        normal_chunks = []  # 标注正常的chunks
        
        # 先找出无法区分的文档
        tag_combinations = defaultdict(list)
        for chunk in all_chunks:
            try:
                if chunk.tags:
                    if isinstance(chunk.tags, str):
                        tags = json.loads(chunk.tags)
                    else:
                        tags = chunk.tags
                    
                    if isinstance(tags, list) and len(tags) > 0:
                        tag_combo = tuple(sorted(tags))
                        tag_combinations[tag_combo].append(chunk)
            except (json.JSONDecodeError, TypeError):
                continue
        
        # 标记无法区分的文档
        indistinguishable_chunk_ids = set()
        for tag_combo, chunks_with_same_tags in tag_combinations.items():
            if len(chunks_with_same_tags) > 1:
                # 按内容长度排序，选择最有代表性的
                sorted_chunks = sorted(chunks_with_same_tags, key=lambda x: len(x.content), reverse=True)
                max_representatives = min(2, len(sorted_chunks))  # 每组最多2个代表进入处理队列
                for chunk in sorted_chunks[:max_representatives]:
                    indistinguishable_chunk_ids.add(chunk.id)
        
        # 分类chunks
        for chunk in all_chunks:
            try:
                if chunk.id in indistinguishable_chunk_ids:
                    indistinguishable_chunks.append(chunk)
                elif chunk.tags:
                    if isinstance(chunk.tags, str):
                        tags = json.loads(chunk.tags)
                    else:
                        tags = chunk.tags
                    
                    if not isinstance(tags, list):
                        error_tagged_chunks.append(chunk)
                    elif len(tags) == 0:
                        untagged_chunks.append(chunk)
                    elif len(tags) < 3:  # 标签数量少于3个认为是标注不足
                        under_tagged_chunks.append(chunk)
                    else:
                        normal_chunks.append(chunk)  # 标注正常的chunks
                else:
                    untagged_chunks.append(chunk)
                    
            except (json.JSONDecodeError, TypeError):
                error_tagged_chunks.append(chunk)
        
        # 智能优先级选择策略 - 优先处理无法区分的文档
        priority_chunks = []
        
        # 1. 最高优先级：无法区分的文档 - 这些文档需要细化标签或引入新标签
        if indistinguishable_chunks:
            # 无法区分的文档获得最高优先级，分配约40%的名额
            max_indistinguishable = min(len(indistinguishable_chunks), max_batch_size // 2)
            priority_chunks.extend(indistinguishable_chunks[:max_indistinguishable])
            logger.info(f"选择了 {len(indistinguishable_chunks[:max_indistinguishable])} 个无法区分文档进行细化处理（最高优先级）")
        
        # 2. 高优先级：错误标签文档 - 需要立即修复
        remaining_slots = max_batch_size - len(priority_chunks)
        if remaining_slots > 0 and error_tagged_chunks:
            max_error_docs = min(len(error_tagged_chunks), remaining_slots // 2)
            priority_chunks.extend(error_tagged_chunks[:max_error_docs])
            remaining_slots -= max_error_docs
            logger.info(f"选择了 {max_error_docs} 个错误标签文档进行修复")
        
        # 3. 中优先级：新信息流处理 - 未标注的chunks
        if remaining_slots > 0 and untagged_chunks:
            new_chunks_count = min(remaining_slots, len(untagged_chunks))
            priority_chunks.extend(untagged_chunks[:new_chunks_count])
            remaining_slots -= new_chunks_count
            logger.info(f"选择了 {new_chunks_count} 个未标注文档进行新信息处理")
        
        # 4. 低优先级：标注不足的文档
        if remaining_slots > 0 and under_tagged_chunks:
            under_tagged_count = min(remaining_slots, len(under_tagged_chunks))
            priority_chunks.extend(under_tagged_chunks[:under_tagged_count])
            remaining_slots -= under_tagged_count
            logger.info(f"选择了 {under_tagged_count} 个标注不足文档进行补充")
        
        # 5. 最低优先级：正常文档的重新评估
        if remaining_slots > 0 and normal_chunks:
            import random
            # 随机选择一些正常chunks进行重新评估，保持系统活力
            random.shuffle(normal_chunks)
            additional_chunks = normal_chunks[:remaining_slots]
            priority_chunks.extend(additional_chunks)
            logger.info(f"选择了 {len(additional_chunks)} 个正常文档进行重新评估")
        
        logger.info(f"文档选择完成: 总计 {len(priority_chunks)} 个文档")
        logger.debug(f"   无法区分: {len([c for c in priority_chunks if c in indistinguishable_chunks])}")
        logger.debug(f"   错误标签: {len([c for c in priority_chunks if c in error_tagged_chunks])}")
        logger.debug(f"   未标注: {len([c for c in priority_chunks if c in untagged_chunks])}")
        logger.debug(f"   标注不足: {len([c for c in priority_chunks if c in under_tagged_chunks])}")
        logger.debug(f"   重新评估: {len([c for c in priority_chunks if c in normal_chunks])}")
        
        # 转换为DocumentInfo
        documents = []
        for chunk in priority_chunks:
            try:
                if chunk.tags:
                    if isinstance(chunk.tags, str):
                        tags = json.loads(chunk.tags)
                    else:
                        tags = chunk.tags
                    
                    if not isinstance(tags, list):
                        tags = []
                else:
                    tags = []
                
                documents.append(DocumentInfo(
                    doc_id=chunk.id,
                    content=chunk.content,
                    current_tags=tags,
                    kb_id=kb_id,
                    chunk_index=chunk.chunk_index
                ))
            except (json.JSONDecodeError, TypeError):
                documents.append(DocumentInfo(
                    doc_id=chunk.id,
                    content=chunk.content,
                    current_tags=[],
                    kb_id=kb_id,
                    chunk_index=chunk.chunk_index
                ))
        
        return documents
    

    
    def _get_default_stats(self, kb_id: str, kb: KnowledgeBase) -> SDTMStats:
        """返回默认的SDTM统计信息（用于没有文档的情况）"""
        
        # 默认质量指标
        default_quality_metrics = QualityMetrics(
            tags_document_distribution={},
            documents_tag_distribution={},
            under_annotated_docs_count=0,
            over_annotated_docs_count=0,
            under_used_tags_count=0,
            over_used_tags_count=0,
            indistinguishable_docs_count=0
        )
        
        # 检查冷启动状态
        cold_start_info = self._check_cold_start_status(kb_id, [])
        
        # 使用统一的进度指标计算方法
        default_progress_metrics = self._calculate_progress_metrics(kb, [], cold_start_info)
        
        # 获取冷启动建议
        abnormal_documents = []
        if cold_start_info['is_cold_start']:
            abnormal_documents = self._get_cold_start_recommendations(cold_start_info)
        
        return SDTMStats(
            progress_metrics=default_progress_metrics,
            quality_metrics=default_quality_metrics,
            abnormal_documents=abnormal_documents,
            last_updated=datetime.now()
        )
    
    def _check_cold_start_status(self, kb_id: str, chunks: List[Chunk]) -> Dict[str, Any]:
        """检查知识库的冷启动状态"""
        from app.services.document_service import DocumentService
        
        doc_service = DocumentService(self.db)
        documents_with_chunks = doc_service.get_kb_documents_with_chunk_count(kb_id)
        
        # 统计各种情况
        total_documents = len(documents_with_chunks)
        documents_without_chunks = [doc for doc in documents_with_chunks if doc['chunk_count'] == 0]
        documents_with_chunks_count = total_documents - len(documents_without_chunks)
        
        # 获取知识库信息
        kb = self.db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
        has_tag_dictionary = kb and kb.tag_dictionary and len(kb.tag_dictionary) > 0
        
        # 判断冷启动类型
        cold_start_type = None
        is_cold_start = False
        
        if total_documents == 0:
            cold_start_type = "no_documents"
            is_cold_start = True
        elif len(documents_without_chunks) == total_documents:
            cold_start_type = "documents_no_chunks"
            is_cold_start = True
        elif not has_tag_dictionary:
            cold_start_type = "no_tag_dictionary"
            is_cold_start = True
        elif len(chunks) == 0:
            cold_start_type = "no_chunks"
            is_cold_start = True
        
        return {
            'is_cold_start': is_cold_start,
            'cold_start_type': cold_start_type,
            'total_documents': total_documents,
            'documents_without_chunks': len(documents_without_chunks),
            'documents_with_chunks': documents_with_chunks_count,
            'has_tag_dictionary': has_tag_dictionary,
            'unprocessed_documents': documents_without_chunks
        }
    
    def _get_cold_start_recommendations(self, cold_start_info: Dict[str, Any]) -> List[AbnormalDocument]:
        """获取冷启动建议 - 专注于标签字典初始化"""
        recommendations = []
        
        cold_start_type = cold_start_info['cold_start_type']
        
        if cold_start_type == "no_documents":
            recommendations.append(AbnormalDocument(
                doc_id="cold_start_no_docs",
                reason="知识库为空，需要上传并摄入文档",
                content="当前知识库没有任何文档。请先：1. 上传文档到知识库 2. 运行完整的文档摄入流程 3. 然后使用SDTM进行智能标注",
                current_tags=["冷启动", "无文档"],
                anomaly_type="cold_start"
            ))
        
        elif cold_start_type == "documents_no_chunks":
            recommendations.append(AbnormalDocument(
                doc_id="cold_start_need_ingestion",
                reason="文档需要完成摄入流程",
                content=f"发现 {cold_start_info['documents_without_chunks']} 个未摄入的文档。请先运行完整的摄入流程（格式转换、截图、图像理解、分块），然后使用SDTM进行智能标注。",
                current_tags=["冷启动", "需要摄入"],
                anomaly_type="cold_start"
            ))
        
        elif cold_start_type == "no_tag_dictionary":
            recommendations.append(AbnormalDocument(
                doc_id="cold_start_dict_init",
                reason="标签字典为空，SDTM可以智能初始化",
                content="文档已摄入但标签字典为空。SDTM可以分析已摄入的chunks内容，智能生成初始标签字典并为所有chunks提供标注。这是SDTM的核心功能。",
                current_tags=["冷启动", "智能初始化"],
                anomaly_type="cold_start"
            ))
        
        elif cold_start_type == "no_chunks":
            recommendations.append(AbnormalDocument(
                doc_id="cold_start_data_error",
                reason="数据不一致，需要重新摄入",
                content="检测到异常状态：有文档但无chunks。请检查摄入流程是否正常，或重新运行完整的文档摄入。",
                current_tags=["冷启动", "数据异常"],
                anomaly_type="cold_start"
            ))
        
        return recommendations