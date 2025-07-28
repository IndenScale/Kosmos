import json
import logging
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models import Fragment, KBFragment, Index, KnowledgeBase, KBModelConfig
from app.schemas.index import IndexResponse, IndexStatsResponse, IndexJobResponse, IndexStatus
from app.services.credential_service import CredentialService
from app.repositories.milvus_repo import MilvusRepository
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class IndexService:
    """索引服务类"""

    def __init__(self, kb_id: str, db: Session):
        self.kb_id = kb_id
        self.db = db
        self.credential_service = CredentialService()
        self.milvus_repo = MilvusRepository()

    async def _get_model_config(self) -> Optional[KBModelConfig]:
        """获取知识库的模型配置"""
        try:
            config = self.db.query(KBModelConfig).filter(
                KBModelConfig.kb_id == self.kb_id
            ).first()
            return config
        except Exception as e:
            logger.error(f"获取模型配置失败: {str(e)}")
            return None

    async def _get_openai_client(self, kb_id: str, model_type: str) -> Optional[AsyncOpenAI]:
        """获取OpenAI客户端"""
        try:
            config = await self._get_model_config()
            if not config:
                return None

            credential_id = None
            if model_type == "embedding":
                credential_id = config.embedding_credential_id
            elif model_type == "llm":
                credential_id = config.llm_credential_id

            if not credential_id:
                return None

            # 获取知识库所有者ID
            kb = self.db.query(KnowledgeBase).filter(KnowledgeBase.id == self.kb_id).first()
            if not kb:
                logger.error(f"知识库 {self.kb_id} 不存在")
                return None

            # 获取凭证信息
            from app.models import ModelAccessCredential
            credential = self.db.query(ModelAccessCredential).filter(ModelAccessCredential.id == credential_id).first()
            if not credential:
                logger.error(f"凭证 {credential_id} 不存在")
                return None

            # 获取解密的API Key
            api_key = self.credential_service.get_decrypted_api_key(self.db, credential_id, kb.owner_id)
            if not api_key:
                return None

            # 使用凭证中的base_url创建客户端
            base_url = credential.base_url.strip() if credential.base_url else "https://api.openai.com/v1"

            return AsyncOpenAI(api_key=api_key, base_url=base_url)

        except Exception as e:
            logger.error(f"获取OpenAI客户端失败: {str(e)}")
            return None

    async def _get_embedding(self, text: str) -> List[float]:
        """生成文本的向量嵌入"""
        client = None
        try:
            client = await self._get_openai_client(self.kb_id, "embedding")
            if not client:
                raise Exception("无法获取嵌入模型客户端")

            # 获取配置中的embedding模型名称
            config = await self._get_model_config()
            if not config or not config.embedding_model_name:
                raise Exception("未配置embedding模型")

            response = await client.embeddings.create(
                model=config.embedding_model_name,
                input=text
            )

            return response.data[0].embedding

        except Exception as e:
            logger.error(f"生成嵌入向量失败: {str(e)}")
            raise Exception(f"生成嵌入向量失败: {str(e)}")
        finally:
            # 确保客户端被正确关闭
            if client:
                try:
                    await client.close()
                except Exception as e:
                    logger.warning(f"关闭embedding客户端时出错: {e}")

    async def _generate_tags(self, content: str, max_tags: int = 20) -> List[str]:
        """生成标签"""
        try:
            # 获取知识库的标签字典
            kb = self.db.query(KnowledgeBase).filter(KnowledgeBase.id == self.kb_id).first()
            if not kb or not kb.tag_dictionary:
                logger.warning(f"知识库 {self.kb_id} 没有配置标签字典")
                return []

            tag_directory = kb.tag_dictionary

            # 尝试使用LLM生成标签
            try:
                return await self._generate_tags_with_llm(content, tag_directory, max_tags)
            except Exception as e:
                logger.warning(f"LLM标签生成失败，使用BM25回退: {str(e)}")
                return self._generate_tags_with_bm25(content, tag_directory, max_tags)

        except Exception as e:
            logger.error(f"标签生成失败: {str(e)}")
            return []

    async def _generate_tags_with_llm(self, content: str, tag_directory: Dict[str, Any], max_tags: int = 20) -> List[str]:
        """使用LLM生成标签"""
        client = None
        try:
            # 获取OpenAI客户端
            client = await self._get_openai_client(self.kb_id, "llm")
            if not client:
                logger.warning("无法获取LLM客户端，使用BM25回退")
                return self._generate_tags_with_bm25(content, tag_directory, max_tags)

            # 获取配置中的LLM模型名称
            config = await self._get_model_config()
            if not config or not config.llm_model_name:
                logger.warning("未配置LLM模型，使用BM25回退")
                return self._generate_tags_with_bm25(content, tag_directory, max_tags)

            # 提取所有可用标签
            all_tags = self._extract_all_tags_from_dictionary(tag_directory)

            # 构建提示词
            tags_text = ", ".join(all_tags[:50])  # 限制标签数量避免提示词过长

            prompt = f"""
请从以下标签列表中选择最适合描述给定内容的标签，最多选择{max_tags}个：

可用标签：{tags_text}

内容：{content[:1000]}

请只返回选中的标签，用逗号分隔，不要包含其他文字。
"""

            # 调用LLM
            response = await client.chat.completions.create(
                model=config.llm_model_name,  # 使用配置中的模型名称
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.3
            )

            # 解析响应
            result_text = response.choices[0].message.content.strip()
            selected_tags = [tag.strip() for tag in result_text.split(",") if tag.strip()]

            # 验证标签是否在可用标签列表中
            valid_tags = [tag for tag in selected_tags if tag in all_tags]

            return valid_tags[:max_tags]

        except Exception as e:
            logger.error(f"LLM标签生成失败: {str(e)}")
            # 回退到BM25
            return self._generate_tags_with_bm25(content, tag_directory, max_tags)
        finally:
            # 确保客户端被正确关闭
            if client:
                try:
                    await client.close()
                except Exception as e:
                    logger.warning(f"关闭LLM客户端时出错: {e}")

    def _extract_all_tags_from_dictionary(self, tag_dict: Dict[str, Any]) -> List[str]:
        """从标签字典中提取所有可用的标签（扁平化）"""
        all_tags = []

        def extract_recursive(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    if isinstance(value, list):
                        # 叶子节点：列表字符串
                        all_tags.extend(value)
                    elif isinstance(value, dict):
                        # 继续递归
                        extract_recursive(value, current_path)
            elif isinstance(obj, list):
                # 直接是列表字符串（深度为1的情况）
                all_tags.extend(obj)

        extract_recursive(tag_dict)
        return list(set(all_tags))  # 去重

    def _generate_tags_with_bm25(self, content: str, tag_directory: Dict[str, Any], max_tags: int = 20) -> List[str]:
        """使用BM25算法生成标签（LLM不可用时的回退方案）"""
        try:
            # 提取所有可用标签
            all_tags = self._extract_all_tags_from_dictionary(tag_directory)

            # 简化的BM25实现：基于关键词匹配
            content_lower = content.lower()
            tag_scores = {}

            # 计算每个标签的相关性分数
            for tag in all_tags:
                if isinstance(tag, str):
                    tag_lower = tag.lower()
                    # 简单的词频统计
                    count = content_lower.count(tag_lower)
                    if count > 0:
                        # 使用简化的TF-IDF权重
                        tag_scores[tag] = count * (1 + len(tag))  # 长标签权重更高

            # 按分数排序并返回前max_tags个标签
            sorted_tags = sorted(tag_scores.items(), key=lambda x: x[1], reverse=True)
            return [tag for tag, score in sorted_tags[:max_tags]]

        except Exception as e:
            logger.error(f"BM25标签生成失败: {str(e)}")
            return []

    async def _create_or_update_index(self, fragment: Fragment, tags: List[str], embedding: List[float]) -> Index:
        """创建或更新索引记录"""
        # 检查是否已存在索引
        existing_index = self.db.query(Index).filter(
            and_(
                Index.kb_id == self.kb_id,
                Index.fragment_id == fragment.id
            )
        ).first()

        if existing_index:
            # 更新现有索引
            existing_index.tags = json.dumps(tags, ensure_ascii=False) if tags else None
            existing_index.content = fragment.raw_content or ""
            existing_index.updated_at = datetime.utcnow()
            index_record = existing_index
        else:
            # 创建新索引
            index_record = Index(
                kb_id=self.kb_id,
                fragment_id=fragment.id,
                tags=json.dumps(tags, ensure_ascii=False) if tags else None,
                content=fragment.raw_content or "",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            self.db.add(index_record)

        self.db.commit()
        self.db.refresh(index_record)

        # 更新Milvus中的向量
        await self._update_milvus_vector(fragment.id, fragment.document_id, tags, embedding)

        # 更新文档的最后索引时间
        self._update_document_ingest_time(fragment.document_id)

        return index_record

    async def _update_milvus_vector(self, fragment_id: str, document_id: str, tags: List[str], embedding: List[float]):
        """更新Milvus中的向量数据"""
        try:
            # 获取或创建collection
            kb = self.db.query(KnowledgeBase).filter(KnowledgeBase.id == self.kb_id).first()
            if not kb:
                raise Exception(f"知识库不存在: {self.kb_id}")

            if not kb.milvus_collection_id:
                # 创建新的collection
                collection_name = self.milvus_repo.create_collection(str(self.kb_id))
                kb.milvus_collection_id = collection_name
                self.db.commit()
            else:
                collection_name = kb.milvus_collection_id

            # 准备向量数据
            vector_data = [{
                "chunk_id": str(fragment_id),  # 使用fragment_id作为chunk_id
                "document_id": str(document_id),
                "tags": tags,
                "embedding": embedding
            }]

            # 插入或更新向量
            self.milvus_repo.insert_chunks(collection_name, vector_data)

        except Exception as e:
            logger.error(f"更新Milvus向量失败: {str(e)}")
            raise Exception(f"更新向量数据库失败: {str(e)}")

    async def create_fragment_index(self, fragment_id: str, force_regenerate: bool = False, max_tags: int = 20, enable_multimodal: bool = False, multimodal_config: dict = None) -> IndexResponse:
        """为单个Fragment创建索引"""
        try:
            # 获取Fragment
            fragment = self.db.query(Fragment).filter(Fragment.id == fragment_id).first()
            if not fragment:
                raise Exception(f"Fragment不存在: {fragment_id}")

            # 检查Fragment是否属于指定知识库
            kb_fragment = self.db.query(KBFragment).filter(
                and_(
                    KBFragment.kb_id == self.kb_id,
                    KBFragment.fragment_id == fragment_id
                )
            ).first()

            if not kb_fragment:
                raise Exception(f"Fragment {fragment_id} 不属于知识库 {self.kb_id}")

            # 目前只处理文本片段
            if fragment.fragment_type != "text":
                logger.info(f"跳过非文本Fragment: {fragment_id} (类型: {fragment.fragment_type})")
                raise Exception(f"暂不支持索引类型: {fragment.fragment_type}")

            # 检查是否已存在索引
            if not force_regenerate:
                existing_index = self.db.query(Index).filter(
                    and_(
                        Index.kb_id == self.kb_id,
                        Index.fragment_id == fragment_id
                    )
                ).first()

                if existing_index:
                    logger.info(f"Fragment {fragment_id} 已存在索引，跳过")
                    return IndexResponse(
                        id=existing_index.id,
                        kb_id=existing_index.kb_id,
                        fragment_id=existing_index.fragment_id,
                        tags=existing_index.tags_list,
                        content=existing_index.content,
                        created_at=existing_index.created_at,
                        updated_at=existing_index.updated_at
                    )

            # 获取文本内容
            content = fragment.raw_content or ""
            if not content.strip():
                logger.warning(f"Fragment {fragment_id} 内容为空，跳过索引")
                raise Exception("Fragment内容为空")

            # 生成标签
            tags = await self._generate_tags(content, max_tags)

            # 生成向量嵌入
            embedding = await self._get_embedding(content)

            # 创建或更新索引
            index_record = await self._create_or_update_index(fragment, tags, embedding)

            logger.info(f"成功为Fragment {fragment_id} 创建索引")
            return IndexResponse(
                id=index_record.id,
                kb_id=index_record.kb_id,
                fragment_id=index_record.fragment_id,
                tags=index_record.tags_list,
                content=index_record.content,
                created_at=index_record.created_at,
                updated_at=index_record.updated_at
            )

        except Exception as e:
            logger.error(f"为Fragment {fragment_id} 创建索引失败: {str(e)}")
            raise Exception(f"索引创建失败: {str(e)}")

    async def batch_index_documents(self, document_ids: List[str], force_regenerate: bool = False, max_tags: int = 20) -> IndexJobResponse:
        """批量为文档的所有Fragment创建索引"""
        try:
            # 获取所有文档的Fragment
            all_fragment_ids = []
            document_fragment_map = {}
            
            for document_id in document_ids:
                # 获取文档的所有文本Fragment
                fragments = self.db.query(Fragment).filter(
                    and_(
                        Fragment.document_id == document_id,
                        Fragment.fragment_type == "text"  # 只处理文本Fragment
                    )
                ).all()
                
                fragment_ids = [f.id for f in fragments]
                document_fragment_map[document_id] = fragment_ids
                all_fragment_ids.extend(fragment_ids)
            
            if not all_fragment_ids:
                logger.warning(f"文档列表中没有找到可索引的Fragment: {document_ids}")
                current_time = datetime.utcnow()
                return IndexJobResponse(
                    job_id=str(uuid.uuid4()),
                    kb_id=self.kb_id,
                    status=IndexStatus.COMPLETED,
                    total_fragments=0,
                    processed_fragments=0,
                    failed_fragments=0,
                    error_message="没有找到可索引的Fragment",
                    created_at=current_time,
                    updated_at=current_time
                )
            
            # 调用现有的批量索引方法
            result = await self.batch_index_fragments(all_fragment_ids, force_regenerate, max_tags)
            
            # 更新结果信息，包含文档信息
            result.error_message = f"批量索引完成: 处理{len(document_ids)}个文档的{result.processed_fragments}个Fragment，失败{result.failed_fragments}个"
            
            logger.info(f"成功为{len(document_ids)}个文档创建索引，共处理{result.processed_fragments}个Fragment")
            return result
            
        except Exception as e:
            logger.error(f"批量索引文档失败: {str(e)}")
            raise Exception(f"批量索引文档失败: {str(e)}")

    async def batch_index_fragments(self, fragment_ids: List[str], force_regenerate: bool = False, max_tags: int = 20) -> IndexJobResponse:
        """批量为Fragment创建索引"""
        try:
            total_fragments = len(fragment_ids)
            processed_fragments = 0
            failed_fragments = 0
            skipped_fragments = 0
            errors = []
            processed_documents = set()  # 记录已处理的文档ID

            for fragment_id in fragment_ids:
                try:
                    # 检查是否已存在索引
                    if not force_regenerate:
                        existing_index = self.db.query(Index).filter(
                            and_(
                                Index.kb_id == self.kb_id,
                                Index.fragment_id == fragment_id
                            )
                        ).first()

                        if existing_index:
                            skipped_fragments += 1
                            continue

                    # 获取Fragment信息以获取document_id
                    fragment = self.db.query(Fragment).filter(Fragment.id == fragment_id).first()
                    if fragment:
                        # 创建索引
                        await self.create_fragment_index(fragment_id, force_regenerate, max_tags)
                        processed_fragments += 1
                        processed_documents.add(fragment.document_id)
                    else:
                        failed_fragments += 1
                        errors.append(f"Fragment {fragment_id}: Fragment不存在")

                except Exception as e:
                    failed_fragments += 1
                    error_msg = f"Fragment {fragment_id}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)

            # 批量更新所有处理过的文档的索引时间
            for document_id in processed_documents:
                self._update_document_ingest_time(document_id)

            current_time = datetime.utcnow()
            return IndexJobResponse(
                job_id=str(uuid.uuid4()),
                kb_id=self.kb_id,
                status=IndexStatus.COMPLETED,
                total_fragments=total_fragments,
                processed_fragments=processed_fragments,
                failed_fragments=failed_fragments,
                error_message=f"批量索引完成: 处理{processed_fragments}个，失败{failed_fragments}个，跳过{skipped_fragments}个" if errors else None,
                created_at=current_time,
                updated_at=current_time
            )

        except Exception as e:
            logger.error(f"批量索引失败: {str(e)}")
            raise Exception(f"批量索引失败: {str(e)}")

    async def get_index_stats(self) -> IndexStatsResponse:
        """获取知识库的索引统计信息"""
        try:
            # 获取Fragment统计
            total_fragments = self.db.query(Fragment).join(KBFragment).filter(
                and_(
                    KBFragment.kb_id == self.kb_id,
                    Fragment.fragment_type == "text"  # 只统计文本Fragment
                )
            ).count()

            # 获取已索引Fragment统计
            indexed_fragments = self.db.query(Index).filter(Index.kb_id == self.kb_id).count()

            pending_fragments = max(0, total_fragments - indexed_fragments)

            # 获取向量数据库中的向量数量
            vector_count = 0
            try:
                kb = self.db.query(KnowledgeBase).filter(KnowledgeBase.id == self.kb_id).first()
                if kb and kb.milvus_collection_id:
                    vector_count = self.milvus_repo.get_collection_count(kb.milvus_collection_id)
            except Exception as e:
                logger.warning(f"获取向量数量失败: {str(e)}")
                vector_count = indexed_fragments  # 回退到使用索引数量

            # 获取最后索引时间
            last_index = self.db.query(Index).filter(Index.kb_id == self.kb_id).order_by(Index.updated_at.desc()).first()
            last_index_time = last_index.updated_at if last_index else None

            return IndexStatsResponse(
                kb_id=self.kb_id,
                total_fragments=total_fragments,
                indexed_fragments=indexed_fragments,
                pending_fragments=pending_fragments,
                vector_count=vector_count,
                last_index_time=last_index_time
            )

        except Exception as e:
            logger.error(f"获取索引统计失败: {str(e)}")
            raise Exception(f"获取索引统计失败: {str(e)}")

    async def delete_fragment_index(self, fragment_id: str) -> bool:
        """删除Fragment的索引"""
        try:
            # 删除SQL中的索引记录
            index_record = self.db.query(Index).filter(
                and_(
                    Index.kb_id == self.kb_id,
                    Index.fragment_id == fragment_id
                )
            ).first()

            if index_record:
                self.db.delete(index_record)
                self.db.commit()

            # 删除Milvus中的向量
            try:
                self.milvus_repo.delete_chunk_by_id(str(self.kb_id), str(fragment_id))
            except Exception as e:
                logger.warning(f"删除Milvus向量失败: {str(e)}")

            return True

        except Exception as e:
            logger.error(f"删除Fragment索引失败: {str(e)}")
            return False

    async def delete_document_index(self, document_id: str) -> bool:
        """删除文档的所有索引"""
        try:
            # 获取文档的所有Fragment
            fragments = self.db.query(Fragment).filter(Fragment.document_id == document_id).all()
            fragment_ids = [f.id for f in fragments]

            if not fragment_ids:
                return True

            # 删除SQL中的索引记录
            self.db.query(Index).filter(
                and_(
                    Index.kb_id == self.kb_id,
                    Index.fragment_id.in_(fragment_ids)
                )
            ).delete(synchronize_session=False)
            self.db.commit()

            # 删除Milvus中的向量
            try:
                self.milvus_repo.delete_vectors_by_document(str(self.kb_id), str(document_id))
            except Exception as e:
                logger.warning(f"删除Milvus向量失败: {str(e)}")

            return True

        except Exception as e:
            logger.error(f"删除文档索引失败: {str(e)}")
            return False

    def _update_document_ingest_time(self, document_id: str):
        """更新文档的最后索引时间
        
        Args:
            document_id: 文档ID
        """
        try:
            from app.models.document import KBDocument
            
            # 更新KBDocument的last_ingest_time字段
            kb_document = self.db.query(KBDocument).filter(
                and_(
                    KBDocument.kb_id == self.kb_id,
                    KBDocument.document_id == document_id
                )
            ).first()
            
            if kb_document:
                kb_document.last_ingest_time = datetime.utcnow()
                self.db.commit()
                logger.info(f"已更新文档 {document_id} 的最后索引时间")
            else:
                logger.warning(f"未找到知识库 {self.kb_id} 中的文档 {document_id}")
                
        except Exception as e:
            logger.error(f"更新文档索引时间失败: {document_id}, 错误: {str(e)}")
            # 不抛出异常，避免影响索引创建的主流程

    async def list_indexed_fragments(self, skip: int = 0, limit: int = 100) -> List[IndexResponse]:
        """列出已索引的Fragment"""
        try:
            indexes = self.db.query(Index).filter(
                Index.kb_id == self.kb_id
            ).offset(skip).limit(limit).all()

            result = []
            for index in indexes:
                result.append(IndexResponse(
                    id=index.id,
                    kb_id=index.kb_id,
                    fragment_id=index.fragment_id,
                    tags=index.tags_list,
                    content=index.content[:200] + "..." if len(index.content) > 200 else index.content,
                    created_at=index.created_at,
                    updated_at=index.updated_at
                ))

            return result

        except Exception as e:
            logger.error(f"获取已索引Fragment列表失败: {str(e)}")
            raise Exception(f"获取已索引Fragment列表失败: {str(e)}")

    async def cleanup_orphan_indexes(self) -> Dict[str, Any]:
        """清理孤立的索引记录
        
        删除那些指向无效fragment_id或无效kb_id的索引记录
        
        Returns:
            Dict containing cleanup statistics
        """
        try:
            cleanup_stats = {
                "total_checked": 0,
                "orphan_by_fragment": 0,
                "orphan_by_kb": 0,
                "total_deleted": 0,
                "deleted_ids": []
            }

            # 获取所有索引记录
            all_indexes = self.db.query(Index).all()
            cleanup_stats["total_checked"] = len(all_indexes)

            # 检查每个索引记录
            indexes_to_delete = []
            
            for index in all_indexes:
                is_orphan = False
                orphan_reason = None
                
                # 检查fragment_id是否有效
                fragment_exists = self.db.query(Fragment).filter(
                    Fragment.id == index.fragment_id
                ).first() is not None
                
                if not fragment_exists:
                    is_orphan = True
                    orphan_reason = "invalid_fragment"
                    cleanup_stats["orphan_by_fragment"] += 1
                
                # 检查kb_id是否有效
                kb_exists = self.db.query(KnowledgeBase).filter(
                    KnowledgeBase.id == index.kb_id
                ).first() is not None
                
                if not kb_exists:
                    is_orphan = True
                    orphan_reason = "invalid_kb"
                    cleanup_stats["orphan_by_kb"] += 1
                
                if is_orphan:
                    indexes_to_delete.append(index.id)

            # 执行删除
            if indexes_to_delete:
                self.db.query(Index).filter(
                    Index.id.in_(indexes_to_delete)
                ).delete(synchronize_session=False)
                
                self.db.commit()
                
                cleanup_stats["total_deleted"] = len(indexes_to_delete)
                cleanup_stats["deleted_ids"] = indexes_to_delete

                logger.info(f"清理了 {len(indexes_to_delete)} 个孤立索引记录")

            return cleanup_stats

        except Exception as e:
            logger.error(f"清理孤立索引记录失败: {str(e)}")
            self.db.rollback()
            raise Exception(f"清理孤立索引记录失败: {str(e)}")