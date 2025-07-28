import time
import json
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from typing import List, Dict, Any, Optional
from app.models import Fragment, KBFragment, Index, KnowledgeBase
from app.repositories.milvus_repo import MilvusRepository
from app.utils.ai_utils import AIUtils
from app.utils.query_parser import QueryParser
from app.utils.reranker import Reranker
from app.utils.deduplicator import Deduplicator
from app.services.credential_service import CredentialService
from app.services.tag_recommendation_service import TagRecommendationService
from app.schemas.search import FragmentType
from app.config import get_logger

logger = get_logger(__name__)

class SearchService:
    """基于Fragment抽象的搜索服务"""

    def __init__(self, db: Session):
        self.db = db
        self.milvus_repo = MilvusRepository()
        self.ai_utils = AIUtils()
        self.reranker = Reranker()
        self.deduplicator = Deduplicator()
        self.tag_recommendation_service = TagRecommendationService(db)
        self.query_parser = QueryParser()
        self.credential_service = CredentialService()  # 不传递db参数

    def get_fragment_by_id(self, fragment_id: str, kb_id: str = None) -> Optional[Dict[str, Any]]:
        """根据ID获取Fragment详情"""
        try:
            # 构建查询
            query = self.db.query(Fragment, Index).join(
                Index, Fragment.id == Index.fragment_id
            )

            if kb_id:
                query = query.filter(Index.kb_id == kb_id)

            query = query.filter(Fragment.id == fragment_id)
            result = query.first()

            if not result:
                return None

            fragment, index = result

            # 构建响应数据
            return {
                "id": fragment.id,
                "kb_id": index.kb_id,
                "document_id": fragment.document_id,
                "fragment_index": fragment.fragment_index,
                "fragment_type": fragment.fragment_type,
                "raw_content": fragment.raw_content,
                "meta_info": fragment.meta_info,
                "tags": index.tags_list,
                "created_at": fragment.created_at,
                "updated_at": fragment.updated_at
            }

        except Exception as e:
            logger.error(f"获取Fragment详情失败: {str(e)}")
            return None

    def search(self, kb_id: str, query: str, top_k: int = 10,
               fragment_types: List[FragmentType] = None,
               must_tags: List[str] = None,
               must_not_tags: List[str] = None,
               like_tags: List[str] = None,
               parse_query: bool = True,
               include_screenshots: bool = False,
               include_figures: bool = False) -> Dict[str, Any]:
        """
        执行语义搜索

        Args:
            kb_id: 知识库ID
            query: 搜索查询字符串
            top_k: 返回结果数量
            fragment_types: Fragment类型过滤，默认为[FragmentType.TEXT]
            must_tags: 必须包含的标签
            must_not_tags: 必须不包含的标签
            like_tags: 偏好标签
            parse_query: 是否解析查询字符串中的标签语法
            include_screenshots: 是否包含相关页面范围内的截图
            include_figures: 是否包含相关页面范围内的插图
        """
        start_time = time.time()

        logger.info(f"开始搜索，知识库ID: {kb_id}, 查询: {query[:100]}..., top_k: {top_k}")

        try:
            # 设置默认值并转换枚举为字符串
            if fragment_types is None:
                fragment_types_str = [FragmentType.TEXT.value]
            else:
                fragment_types_str = [ft.value for ft in fragment_types]
            
            if must_tags is None:
                must_tags = []
            if must_not_tags is None:
                must_not_tags = []
            if like_tags is None:
                like_tags = []

            query_parse_result = None
            search_text = query

            # 1. 解析查询（如果启用查询解析）
            if parse_query and query:
                parsed_query = self.query_parser.parse(query)
                query_parse_result = self.query_parser.format_parse_result(parsed_query)

                # 使用解析后的文本查询
                search_text = parsed_query.text

                # 合并解析出的标签和传入的标签
                must_tags = list(set(must_tags + parsed_query.must_tags))
                must_not_tags = list(set(must_not_tags + parsed_query.must_not_tags))
                like_tags = list(set(like_tags + parsed_query.like_tags))

                logger.info(f"查询解析结果: text='{search_text}', must_tags={must_tags}, must_not_tags={must_not_tags}, like_tags={like_tags}")

            # 如果没有实际的文本查询，返回空结果
            if not search_text.strip():
                return self._empty_search_result("查询文本不能为空", query_parse_result)

            # 2. 获取嵌入向量
            query_vector = self._get_embedding(kb_id, search_text)
            if not query_vector:
                return self._empty_search_result("无法获取查询向量", query_parse_result)

            # 3. 从Milvus检索向量相似结果
            milvus_results = self._retrieve_from_milvus(
                kb_id, query_vector, must_tags, must_not_tags, top_k * 3
            )

            if not milvus_results:
                return self._empty_search_result("未找到相关结果", query_parse_result)

            # 4. 获取Fragment详细信息并过滤类型
            detailed_results = self._get_detailed_results(
                milvus_results, kb_id, fragment_types_str, top_k * 2
            )

            if not detailed_results:
                return self._empty_search_result("未找到匹配的Fragment", query_parse_result)

            # 5. 重排序（如果有偏好标签）
            if like_tags:
                detailed_results = self.reranker.rerank(detailed_results, like_tags)

            # 6. 去重处理
            deduplicated_results = self.deduplicator.deduplicate_results(detailed_results)

            # 7. 截取最终结果
            final_results = deduplicated_results[:top_k]

            # 8. 生成推荐标签
            recommended_tags = self.tag_recommendation_service.generate_recommendations(final_results)

            search_time = (time.time() - start_time) * 1000  # 转换为毫秒

            logger.info(f"搜索完成，原始结果: {len(detailed_results)}, 去重后: {len(deduplicated_results)}, 最终返回: {len(final_results)}")

            # 9. 构建最终结果，根据参数决定是否包含相关视觉内容
            final_search_results = []
            for result in final_results:
                # 基础结果
                search_result = {
                    "fragment_id": result["fragment_id"],
                    "document_id": result["document_id"],
                    "fragment_type": result["fragment_type"],
                    "content": result["content"],
                    "tags": result["tags"],
                    "score": result["score"],
                    "meta_info": result["meta_info"],
                    "source_file_name": result.get("source_file_name")
                }
                
                # 如果需要包含视觉内容，添加相关的截图和插图
                if include_screenshots or include_figures:
                    meta_info = result.get("meta_info", {})
                    page_start = meta_info.get("page_start")
                    page_end = meta_info.get("page_end")
                    
                    if page_start is not None and page_end is not None:
                        search_result["page_range"] = {
                            "start": page_start,
                            "end": page_end
                        }
                        
                        # 获取相关的视觉Fragment
                        visual_fragments = self._get_related_visual_fragments(
                            kb_id=kb_id,
                            document_id=result["document_id"],
                            page_start=page_start,
                            page_end=page_end,
                            include_screenshots=include_screenshots,
                            include_figures=include_figures
                        )
                        
                        search_result["related_screenshots"] = visual_fragments["screenshots"]
                        search_result["related_figures"] = visual_fragments["figures"]
                
                final_search_results.append(search_result)
            
            # 返回统一格式的结果
            result = {
                "results": final_search_results,
                "recommended_tags": recommended_tags,
                "stats": {
                    "original_count": len(detailed_results),
                    "deduplicated_count": len(deduplicated_results),
                    "final_count": len(final_results),
                    "search_time_ms": search_time,
                    "contextual_mode": include_screenshots or include_figures
                }
            }

            # 添加查询解析结果
            if query_parse_result:
                result["query_parse_result"] = query_parse_result

            return result

        except Exception as e:
            logger.error(f"搜索失败: {str(e)}")
            return self._empty_search_result(f"搜索失败: {str(e)}", query_parse_result)

    def _get_embedding(self, kb_id: str, text: str) -> Optional[List[float]]:
        """获取文本的嵌入向量"""
        try:
            # 获取知识库的模型配置
            from app.models.credential import KBModelConfig
            from app.models.knowledge_base import KnowledgeBase
            from app.models.credential import ModelAccessCredential
            from openai import OpenAI

            # 获取知识库配置
            config = self.db.query(KBModelConfig).filter(
                KBModelConfig.kb_id == kb_id
            ).first()

            if not config or not config.embedding_credential_id:
                logger.error(f"知识库 {kb_id} 未配置嵌入模型")
                return None

            # 获取知识库所有者ID
            kb = self.db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
            if not kb:
                logger.error(f"知识库 {kb_id} 不存在")
                return None

            # 获取凭证信息
            credential = self.db.query(ModelAccessCredential).filter(
                ModelAccessCredential.id == config.embedding_credential_id
            ).first()
            if not credential:
                logger.error(f"凭证 {config.embedding_credential_id} 不存在")
                return None

            # 获取解密的API Key
            api_key = self.credential_service.get_decrypted_api_key(
                self.db, config.embedding_credential_id, kb.owner_id
            )
            if not api_key:
                logger.error(f"无法获取解密的API Key")
                return None

            # 创建OpenAI客户端
            base_url = credential.base_url.strip() if credential.base_url else "https://api.openai.com/v1"
            client = OpenAI(api_key=api_key, base_url=base_url)

            # 获取嵌入向量
            model_name = config.embedding_model_name or "text-embedding-ada-002"
            response = client.embeddings.create(
                model=model_name,
                input=text
            )

            return response.data[0].embedding

        except Exception as e:
            logger.error(f"获取嵌入向量失败: {str(e)}")
            return None

    def _retrieve_from_milvus(self, kb_id: str, query_vector: List[float],
                             must_tags: List[str],
                             must_not_tags: List[str],
                             top_k: int) -> List[Dict[str, Any]]:
        """从Milvus检索向量相似结果"""
        try:
            return self.milvus_repo.retrieve_with_filter(
                kb_id=kb_id,
                query_vector=query_vector,
                must_tags=must_tags,
                must_not_tags=must_not_tags,
                top_k=top_k
            )
        except Exception as e:
            logger.error(f"Milvus检索失败: {str(e)}")
            return []

    def _get_detailed_results(self, milvus_results: List[Dict[str, Any]],
                             kb_id: str, fragment_types: List[str],
                             limit: int) -> List[Dict[str, Any]]:
        """获取Fragment详细信息并过滤类型"""
        if not milvus_results:
            return []

        # 提取fragment_ids（在新的实现中，chunk_id实际上是fragment_id）
        fragment_ids = [r.get("chunk_id") for r in milvus_results[:limit] if r.get("chunk_id")]

        if not fragment_ids:
            return []

        try:
            # 查询Fragment和Index信息
            query = self.db.query(Fragment, Index).join(
                Index, Fragment.id == Index.fragment_id
            ).filter(
                and_(
                    Fragment.id.in_(fragment_ids),
                    Index.kb_id == kb_id
                )
            )

            # 如果指定了fragment类型，添加过滤条件
            if fragment_types:
                query = query.filter(Fragment.fragment_type.in_(fragment_types))

            results = query.all()

            # 构建fragment_id到结果的映射
            fragment_map = {}
            for fragment, index in results:
                fragment_map[fragment.id] = {
                    "fragment": fragment,
                    "index": index
                }

            # 构建最终结果，保持Milvus返回的顺序
            detailed_results = []
            # 缓存文档文件名，避免重复查询
            document_filename_cache = {}
            
            for milvus_result in milvus_results:
                fragment_id = milvus_result.get("chunk_id")
                if fragment_id in fragment_map:
                    fragment_data = fragment_map[fragment_id]
                    fragment = fragment_data["fragment"]
                    index = fragment_data["index"]

                    # 获取文档文件名（使用缓存）
                    document_id = fragment.document_id
                    if document_id not in document_filename_cache:
                        document_filename_cache[document_id] = self._get_source_file_name(document_id)
                    source_file_name = document_filename_cache[document_id]

                    detailed_results.append({
                        "fragment_id": fragment.id,
                        "document_id": fragment.document_id,
                        "fragment_type": fragment.fragment_type,
                        "content": index.content,
                        "tags": index.tags_list,
                        "score": milvus_result.get("rerank_score", milvus_result.get("score", 0.0)),
                        "meta_info": fragment.meta_info,
                        "source_file_name": source_file_name
                    })

            return detailed_results

        except Exception as e:
            logger.error(f"获取Fragment详细信息失败: {str(e)}")
            return []

    def _get_related_visual_fragments(self, kb_id: str, document_id: str, 
                                     page_start: int, page_end: int,
                                     include_screenshots: bool = False,
                                     include_figures: bool = False) -> Dict[str, List[Dict[str, Any]]]:
        """
        根据页面范围获取相关的截图和插图
        
        Args:
            kb_id: 知识库ID
            document_id: 文档ID
            page_start: 起始页面
            page_end: 结束页面
            include_screenshots: 是否包含截图
            include_figures: 是否包含插图
            
        Returns:
            包含screenshots和figures列表的字典
        """
        result = {
            "screenshots": [],
            "figures": []
        }
        
        if not (include_screenshots or include_figures):
            return result
            
        try:
            # 构建查询条件
            fragment_types = []
            if include_screenshots:
                fragment_types.append("screenshot")
            if include_figures:
                fragment_types.append("figure")
                
            if not fragment_types:
                return result
            
            # 直接查询Fragment表，不依赖Index表
            # 因为视觉Fragment（如figure）可能没有对应的Index记录
            from app.models.fragment import KBFragment
            
            query = self.db.query(Fragment).join(
                KBFragment, Fragment.id == KBFragment.fragment_id
            ).filter(
                and_(
                    Fragment.document_id == document_id,
                    KBFragment.kb_id == kb_id,
                    Fragment.fragment_type.in_(fragment_types)
                )
            )
            
            visual_fragments = query.all()
            
            logger.info(f"找到 {len(visual_fragments)} 个视觉Fragment，类型: {fragment_types}")
            
            # 获取文档的原始文件名
            source_file_name = self._get_source_file_name(document_id)
            
            for fragment in visual_fragments:
                # 检查页面范围是否重叠
                if self._is_page_range_overlapping(fragment.meta_info, page_start, page_end):
                    # 尝试从Index表获取内容，如果没有则使用raw_content
                    content = ""
                    tags = []
                    
                    # 尝试获取Index中的内容
                    index_record = self.db.query(Index).filter(
                        and_(
                            Index.fragment_id == fragment.id,
                            Index.kb_id == kb_id
                        )
                    ).first()
                    
                    if index_record:
                        content = index_record.content or ""
                        tags = index_record.tags_list or []
                    else:
                        # 如果没有Index记录，使用Fragment的raw_content
                        content = fragment.raw_content or ""
                        # 从meta_info中提取标签
                        if fragment.meta_info:
                            tags = fragment.meta_info.get("tags", [])
                    
                    # 获取Fragment在同类型中的索引位置
                    fragment_index_by_type = self._get_fragment_index_by_type(
                        document_id, fragment.fragment_type, fragment.id
                    )
                    
                    # 从meta_info获取页面信息
                    fragment_page_start = fragment.meta_info.get("page_start", 1) if fragment.meta_info else 1
                    fragment_page_end = fragment.meta_info.get("page_end", 1) if fragment.meta_info else 1
                    
                    # 生成可读的片段名称
                    figure_name = self._generate_figure_name(
                        source_file_name or "unknown",
                        fragment.fragment_type,
                        fragment_index_by_type,
                        fragment_page_start,
                        fragment_page_end
                    )
                    
                    fragment_data = {
                        "fragment_id": fragment.id,
                        "document_id": fragment.document_id,
                        "fragment_type": fragment.fragment_type,
                        "content": content,
                        "tags": tags,
                        "score": 1.0,  # 相关性分数设为1.0
                        "meta_info": fragment.meta_info,
                        "source_file_name": source_file_name,
                        "figure_name": figure_name
                    }
                    
                    if fragment.fragment_type == "screenshot":
                        result["screenshots"].append(fragment_data)
                    elif fragment.fragment_type == "figure":
                        result["figures"].append(fragment_data)
                        
                    logger.info(f"添加视觉Fragment: {fragment.fragment_type}, ID: {fragment.id}, 名称: {figure_name}")
                        
        except Exception as e:
            logger.error(f"获取相关视觉Fragment失败: {str(e)}")
            
        logger.info(f"最终返回: {len(result['screenshots'])} 个截图, {len(result['figures'])} 个插图")
        return result
    
    def _get_source_file_name(self, document_id: str) -> Optional[str]:
        """获取文档的原始文件名"""
        try:
            from app.models.document import Document
            
            document = self.db.query(Document).filter(Document.id == document_id).first()
            if document:
                return document.filename
            return None
        except Exception as e:
            logger.error(f"获取文件名失败: {str(e)}")
            return None

    def _generate_figure_name(self, source_file_name: str, fragment_type: str, 
                             fragment_index: int, page_start: int, page_end: int) -> str:
        """
        生成可读的片段名称
        格式: {source_file_name}_{fragment_type}_{fragment_index}_page_{page_start}-{page_end}
        """
        try:
            # 移除文件扩展名
            if source_file_name and '.' in source_file_name:
                base_name = source_file_name.rsplit('.', 1)[0]
            else:
                base_name = source_file_name or "unknown"
            
            # 构建片段名称
            if page_start == page_end:
                page_part = f"page_{page_start}"
            else:
                page_part = f"page_{page_start}-{page_end}"
            
            return f"{base_name}_{fragment_type}_{fragment_index}_{page_part}"
        except Exception as e:
            logger.error(f"生成片段名称失败: {str(e)}")
            return f"{fragment_type}_{fragment_index}"

    def _get_fragment_index_by_type(self, document_id: str, fragment_type: str, 
                                   target_fragment_id: str) -> int:
        """获取同类型Fragment中的索引位置"""
        try:
            # 查询同一文档中相同类型的Fragment，按fragment_index排序
            fragments = self.db.query(Fragment).filter(
                and_(
                    Fragment.document_id == document_id,
                    Fragment.fragment_type == fragment_type
                )
            ).order_by(Fragment.fragment_index).all()
            
            # 找到目标Fragment在同类型中的位置
            for i, fragment in enumerate(fragments, 1):
                if fragment.id == target_fragment_id:
                    return i
            
            return 1  # 默认返回1
        except Exception as e:
            logger.error(f"获取Fragment类型索引失败: {str(e)}")
            return 1

    def _is_page_range_overlapping(self, meta_info: Dict[str, Any], 
                                  target_start: int, target_end: int) -> bool:
        """
        检查Fragment的页面范围是否与目标页面范围重叠
        
        Args:
            meta_info: Fragment的元信息
            target_start: 目标起始页面
            target_end: 目标结束页面
            
        Returns:
            是否重叠
        """
        if not meta_info:
            return False
            
        fragment_start = meta_info.get("page_start")
        fragment_end = meta_info.get("page_end")
        
        if fragment_start is None or fragment_end is None:
            return False
            
        # 检查页面范围是否重叠
        # 重叠条件：fragment_start <= target_end and fragment_end >= target_start
        return fragment_start <= target_end and fragment_end >= target_start

    def _empty_search_result(self, error_message: str = "", query_parse_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """返回空的搜索结果"""
        result = {
            "results": [],
            "recommended_tags": [],
            "stats": {
                "original_count": 0,
                "deduplicated_count": 0,
                "final_count": 0,
                "search_time_ms": 0.0
            },
            "error": error_message
        }

        # 添加查询解析结果
        if query_parse_result:
            result["query_parse_result"] = query_parse_result

        return result

    def get_kb_fragments_stats(self, kb_id: str) -> Dict[str, Any]:
        """获取知识库Fragment统计信息"""
        try:
            # 总Fragment数量
            total_fragments = self.db.query(Fragment).join(
                KBFragment, Fragment.id == KBFragment.fragment_id
            ).filter(KBFragment.kb_id == kb_id).count()

            # 按类型统计
            type_stats = self.db.query(
                Fragment.fragment_type,
                func.count(Fragment.id).label('count')
            ).join(
                KBFragment, Fragment.id == KBFragment.fragment_id
            ).filter(
                KBFragment.kb_id == kb_id
            ).group_by(Fragment.fragment_type).all()

            # 激活的Fragment数量（meta_info中activated为true）
            activated_fragments = self.db.query(Fragment).join(
                KBFragment, Fragment.id == KBFragment.fragment_id
            ).filter(
                and_(
                    KBFragment.kb_id == kb_id,
                    Fragment.meta_info.op('->>')('activated') == 'true'
                )
            ).count()

            # 构建统计结果
            stats = {
                "kb_id": kb_id,
                "total_fragments": total_fragments,
                "text_fragments": 0,
                "screenshot_fragments": 0,
                "figure_fragments": 0,
                "activated_fragments": activated_fragments,
                "last_updated": None
            }

            # 填充类型统计
            for fragment_type, count in type_stats:
                if fragment_type == "text":
                    stats["text_fragments"] = count
                elif fragment_type == "screenshot":
                    stats["screenshot_fragments"] = count
                elif fragment_type == "figure":
                    stats["figure_fragments"] = count

            # 获取最后更新时间
            last_updated = self.db.query(
                func.max(Fragment.updated_at)
            ).join(
                KBFragment, Fragment.id == KBFragment.fragment_id
            ).filter(KBFragment.kb_id == kb_id).scalar()

            if last_updated:
                stats["last_updated"] = last_updated

            return stats

        except Exception as e:
            logger.error(f"获取Fragment统计信息失败: {str(e)}")
            return {
                "kb_id": kb_id,
                "total_fragments": 0,
                "text_fragments": 0,
                "screenshot_fragments": 0,
                "figure_fragments": 0,
                "activated_fragments": 0,
                "last_updated": None,
                "error": str(e)
            }