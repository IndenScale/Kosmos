"""
Fragment解析服务
文件: fragment_parser_service.py
创建时间: 2025-07-26
描述: 提供Fragment解析的核心服务功能
"""

import logging
import asyncio
import time
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.fragment import Fragment, KBFragment
from app.models.document import Document, KBDocument
from app.models.knowledge_base import KnowledgeBase
from app.parsers import parser_factory, ParsedFragment
from app.schemas.fragment import FragmentType, FragmentResponse, FragmentListResponse, FragmentUpdate, FragmentStatsResponse
from app.utils.exceptions import ValidationError, ProcessingError


class FragmentParserService:
    """Fragment解析服务"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def parse_document_fragments(
        self,
        db: Session,
        kb_id: str,
        document_id: str,
        force_reparse: bool = False
    ) -> Dict[str, Any]:
        """
        解析文档并创建Fragment

        Args:
            db: 数据库会话
            kb_id: 知识库ID
            document_id: 文档ID
            force_reparse: 是否强制重新解析（包括处理重复内容）

        Returns:
            解析结果字典
        """
        start_time = time.time()

        try:
            # 验证知识库
            kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
            if not kb:
                raise ValidationError(f"知识库不存在: {kb_id}")

            # 验证文档存在
            document = db.query(Document).filter(Document.id == document_id).first()
            if not document:
                raise ValidationError(f"文档不存在: {document_id}")

            # 验证文档是否属于该知识库
            kb_document = db.query(KBDocument).filter(
                and_(KBDocument.kb_id == kb_id, KBDocument.document_id == document_id)
            ).first()
            if not kb_document:
                raise ValidationError(f"文档不属于该知识库: {document_id}")

            # 获取文件URL（从物理文档中获取）
            file_url = document.physical_file.url if document.physical_file else None
            if not file_url:
                raise ProcessingError(f"无法获取文件URL: {document_id}")

            # 检查是否已经存在相同content_hash的fragments
            content_hash = document.content_hash
            existing_fragments_by_hash = db.query(Fragment).filter(
                Fragment.content_hash == content_hash
            ).all()

            # 检查当前文档是否已经解析过
            existing_fragments_current = db.query(Fragment).filter(
                Fragment.document_id == document_id
            ).count()

            # 如果不是强制重新解析，检查是否需要跳过
            if not force_reparse:
                # 如果存在相同内容的fragments，跳过解析
                if existing_fragments_by_hash:
                    parse_duration = int((time.time() - start_time) * 1000)
                    self.logger.info(f"发现相同内容的文档已解析，跳过: {document_id} (content_hash: {content_hash})")
                    return {
                        'document_id': document_id,
                        'status': 'skipped',
                        'reason': 'duplicate_content',
                        'content_hash': content_hash,
                        'existing_fragments': len(existing_fragments_by_hash),
                        'parse_duration_ms': parse_duration
                    }

                # 如果当前文档已经解析过，跳过解析
                if existing_fragments_current > 0:
                    parse_duration = int((time.time() - start_time) * 1000)
                    self.logger.info(f"文档已解析过，跳过: {document_id}")
                    return {
                        'document_id': document_id,
                        'status': 'skipped',
                        'reason': 'already_parsed',
                        'existing_fragments': existing_fragments_current,
                        'parse_duration_ms': parse_duration
                    }
            else:
                # 强制重新解析时，如果存在相同内容哈希的fragments，需要删除它们
                if existing_fragments_by_hash:
                    self.logger.info(f"强制重新解析，删除相同内容的fragments: content_hash={content_hash}")
                    # 获取所有相同content_hash的文档ID
                    affected_doc_ids = list(set(f.document_id for f in existing_fragments_by_hash))
                    for doc_id in affected_doc_ids:
                        self.delete_document_fragments(db, doc_id)

            # 开始事务性操作
            # 使用savepoint确保可以回滚到解析开始前的状态
            savepoint = db.begin_nested()

            try:
                # 1. 删除现有的Fragment及其所有依赖（如果强制重新解析）
                if force_reparse:
                    self.logger.info(f"强制重新解析，删除现有Fragment: {document_id}")
                    deleted_count = self.delete_document_fragments(db, document_id)
                    if deleted_count > 0:
                        self.logger.info(f"已删除 {deleted_count} 个现有Fragment")

                # 2. 获取解析器（使用物理文档的URL）
                parser = parser_factory.get_parser(file_url, db, kb_id)
                if not parser:
                    raise ProcessingError(f"未找到合适的解析器: {file_url}")

                # 3. 解析文档
                self.logger.info(f"开始解析文档: {file_url}")
                parsed_fragments = parser.parse(file_url)

                if not parsed_fragments:
                    parse_duration = int((time.time() - start_time) * 1000)
                    self.logger.warning(f"文档解析结果为空: {file_url}")
                    # 如果解析结果为空，回滚到savepoint
                    savepoint.rollback()
                    return {
                        'document_id': document_id,
                        'status': 'empty',
                        'fragments_created': 0,
                        'parse_duration_ms': parse_duration
                    }

                # 4. 创建新的Fragment
                content_hash = document.content_hash
                created_fragments = []

                for parsed_fragment in parsed_fragments:
                    fragment = self._create_fragment_from_parsed(
                        parsed_fragment,
                        document_id,
                        content_hash
                    )
                    db.add(fragment)
                    created_fragments.append(fragment)

                # 5. 提交Fragment以生成ID
                db.flush()

                # 6. 创建知识库-Fragment关联
                for fragment in created_fragments:
                    kb_fragment = KBFragment(
                        kb_id=kb_id,
                        fragment_id=fragment.id
                    )
                    db.add(kb_fragment)

                # 7. 提交事务
                savepoint.commit()
                db.commit()

                parse_duration = int((time.time() - start_time) * 1000)
                self.logger.info(f"文档解析完成: {file_url}, 创建Fragment: {len(created_fragments)}个, 耗时: {parse_duration}ms")

                return {
                    'document_id': document_id,
                    'status': 'success',
                    'fragments_created': len(created_fragments),
                    'parser_used': parser.__class__.__name__,
                    'parse_duration_ms': parse_duration
                }

            except Exception as inner_e:
                # 回滚到savepoint，恢复到解析开始前的状态
                savepoint.rollback()
                raise inner_e

        except Exception as e:
            db.rollback()
            parse_duration = int((time.time() - start_time) * 1000)
            self.logger.error(f"文档解析失败: {document_id}, 耗时: {parse_duration}ms, 错误: {e}")
            raise ProcessingError(f"文档解析失败: {str(e)}")

    async def parse_multiple_documents(
        self,
        db: Session,
        kb_id: str,
        document_ids: List[str],
        force_reparse: bool = False,
        max_concurrent: int = 3
    ) -> Dict[str, Any]:
        """
        批量解析多个文档的Fragment

        Args:
            db: 数据库会话
            kb_id: 知识库ID
            document_ids: 文档ID列表
            force_reparse: 是否强制重新解析（包括处理重复内容）
            max_concurrent: 最大并发数

        Returns:
            批量解析结果
        """
        try:
            # 验证知识库
            kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
            if not kb:
                raise ValidationError(f"知识库不存在: {kb_id}")

            # 验证文档存在性和知识库关联
            existing_docs = db.query(Document.id).join(KBDocument).filter(
                and_(Document.id.in_(document_ids), KBDocument.kb_id == kb_id)
            ).all()
            existing_doc_ids = [doc.id for doc in existing_docs]

            missing_docs = set(document_ids) - set(existing_doc_ids)
            if missing_docs:
                self.logger.warning(f"部分文档不存在: {missing_docs}")

            # 创建解析任务
            semaphore = asyncio.Semaphore(max_concurrent)

            async def parse_single_doc(doc_id: str):
                async with semaphore:
                    try:
                        return await self.parse_document_fragments(
                            db, kb_id, doc_id, force_reparse
                        )
                    except Exception as e:
                        self.logger.error(f"文档解析失败: {doc_id}, 错误: {e}")
                        return {
                            'document_id': doc_id,
                            'status': 'error',
                            'error': str(e)
                        }

            # 执行批量解析
            self.logger.info(f"开始批量解析: {len(existing_doc_ids)}个文档")
            results = await asyncio.gather(
                *[parse_single_doc(doc_id) for doc_id in existing_doc_ids],
                return_exceptions=True
            )

            # 统计结果
            success_count = sum(1 for r in results if isinstance(r, dict) and r.get('status') == 'success')
            error_count = sum(1 for r in results if isinstance(r, dict) and r.get('status') == 'error')
            skipped_count = sum(1 for r in results if isinstance(r, dict) and r.get('status') == 'skipped')
            empty_count = sum(1 for r in results if isinstance(r, dict) and r.get('status') == 'empty')

            total_fragments = sum(
                r.get('fragments_created', 0) for r in results
                if isinstance(r, dict) and 'fragments_created' in r
            )

            return {
                'kb_id': kb_id,
                'total_documents': len(document_ids),
                'processed_documents': len(existing_doc_ids),
                'missing_documents': len(missing_docs),
                'success_count': success_count,
                'error_count': error_count,
                'skipped_count': skipped_count,
                'empty_count': empty_count,
                'total_fragments_created': total_fragments,
                'results': results,
                'missing_document_ids': list(missing_docs)
            }

        except Exception as e:
            self.logger.error(f"批量解析失败: {kb_id}, 错误: {e}")
            raise ProcessingError(f"批量解析失败: {str(e)}")

    def get_parse_status(self, db: Session, document_id: str) -> Dict[str, Any]:
        """
        获取文档的解析状态

        Args:
            db: 数据库会话
            document_id: 文档ID

        Returns:
            解析状态信息
        """
        try:
            # 验证文档
            document = db.query(Document).filter(Document.id == document_id).first()
            if not document:
                raise ValidationError(f"文档不存在: {document_id}")

            # 获取文档所属的知识库
            kb_document = db.query(KBDocument).filter(
                KBDocument.document_id == document_id
            ).first()
            if not kb_document:
                raise ValidationError(f"文档未关联到知识库: {document_id}")

            kb_id = kb_document.kb_id

            # 获取Fragment统计
            fragments = db.query(Fragment).filter(Fragment.document_id == document_id).all()

            # 按类型统计
            type_stats = {}
            for fragment in fragments:
                ftype = fragment.fragment_type
                if ftype not in type_stats:
                    type_stats[ftype] = 0
                type_stats[ftype] += 1

            # 获取文件URL
            file_url = document.physical_file.url if document.physical_file else None

            # 检查文件是否支持解析
            is_supported = parser_factory.is_supported_file(file_url) if file_url else False
            parser_info = parser_factory.get_parser_info(file_url) if file_url else None

            return {
                 'document_id': document_id,
                 'document_name': document.filename,
                 'file_url': file_url,
                 'is_parsed': len(fragments) > 0,
                 'fragment_count': len(fragments),
                 'fragment_types': type_stats,
                 'is_supported': is_supported,
                 'parser_info': parser_info,
                 'last_modified': document.created_at.isoformat() if document.created_at else None
             }

        except Exception as e:
            self.logger.error(f"获取解析状态失败: {document_id}, 错误: {e}")
            raise ProcessingError(f"获取解析状态失败: {str(e)}")

    def get_kb_parse_stats(self, db: Session, kb_id: str) -> Dict[str, Any]:
        """
        获取知识库的解析统计

        Args:
            db: 数据库会话
            kb_id: 知识库ID

        Returns:
            知识库解析统计
        """
        try:
            # 验证知识库
            kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
            if not kb:
                raise ValidationError(f"知识库不存在: {kb_id}")

            # 获取文档统计
            total_docs = db.query(Document).join(KBDocument).filter(KBDocument.kb_id == kb_id).count()

            # 获取已解析的文档 - 通过KBFragment关联查询
            parsed_docs = db.query(Document.id).join(KBDocument).filter(
                and_(
                    KBDocument.kb_id == kb_id,
                    Document.id.in_(
                        db.query(Fragment.document_id).join(KBFragment).filter(
                            KBFragment.kb_id == kb_id
                        ).distinct()
                    )
                )
            ).count()

            # 失败的文档数量 - 由于没有错误状态字段，暂时设为0
            failed_docs = 0

            # 获取Fragment统计 - 通过KBFragment关联表查询
            fragments = db.query(Fragment).join(KBFragment).filter(KBFragment.kb_id == kb_id).all()

            # 按类型统计Fragment
            type_stats = {}
            for fragment in fragments:
                ftype = fragment.fragment_type
                if ftype not in type_stats:
                    type_stats[ftype] = 0
                type_stats[ftype] += 1

            # 获取支持的文档
            documents = db.query(Document).join(KBDocument).filter(KBDocument.kb_id == kb_id).all()
            supported_docs = sum(
                1 for doc in documents
                if doc.physical_file and parser_factory.is_supported_file(doc.physical_file.url)
            )

            # 获取最后更新时间
            last_updated = None
            if fragments:
                last_updated = max(
                    (f.updated_at for f in fragments if f.updated_at),
                    default=None
                )

            return {
                'kb_id': kb_id,
                'kb_name': kb.name if hasattr(kb, 'name') else kb_id,
                'total_documents': total_docs,
                'parsed_documents': parsed_docs,
                'pending_documents': total_docs - parsed_docs - failed_docs,
                'failed_documents': failed_docs,
                'total_fragments': len(fragments),
                'fragment_types': type_stats,
                'parse_coverage': round(parsed_docs / total_docs * 100, 2) if total_docs > 0 else 0,
                'last_updated': last_updated
            }

        except Exception as e:
            self.logger.error(f"获取知识库解析统计失败: {kb_id}, 错误: {e}")
            raise ProcessingError(f"获取知识库解析统计失败: {str(e)}")

    def _create_fragment_from_parsed(
        self,
        parsed_fragment: ParsedFragment,
        document_id: str,
        content_hash: str
    ) -> Fragment:
        """从解析结果创建Fragment实例"""
        return Fragment(
            content_hash=content_hash,
            document_id=document_id,
            fragment_type=parsed_fragment.fragment_type,
            raw_content=parsed_fragment.raw_content,
            meta_info=parsed_fragment.meta_info,
            fragment_index=parsed_fragment.fragment_index
        )

    def delete_document_fragments(self, db: Session, document_id: str) -> int:
        """
        删除文档的所有Fragment及其相关依赖

        Args:
            db: 数据库会话
            document_id: 文档ID

        Returns:
            删除的Fragment数量
        """
        try:
            # 获取要删除的Fragment详细信息
            fragments = db.query(Fragment).filter(
                Fragment.document_id == document_id
            ).all()

            if not fragments:
                self.logger.info(f"文档无现有Fragment需要删除: {document_id}")
                return 0

            fragment_ids = [f.id for f in fragments]

            # 统计各类型Fragment数量
            type_stats = {}
            for fragment in fragments:
                ftype = fragment.fragment_type
                type_stats[ftype] = type_stats.get(ftype, 0) + 1

            # 记录删除前的统计信息
            stats_str = ", ".join([f"{ftype}: {count}个" for ftype, count in type_stats.items()])
            self.logger.info(f"开始删除文档Fragment: {document_id}, 共{len(fragments)}个Fragment ({stats_str})")

            # 1. 首先删除Index条目 (index_entries表)
            # 这是最重要的步骤，必须在删除fragments之前完成
            from app.models.index import Index
            index_deleted = db.query(Index).filter(
                Index.fragment_id.in_(fragment_ids)
            ).delete(synchronize_session=False)

            # 2. 删除KBFragment关联
            kb_fragment_deleted = db.query(KBFragment).filter(
                KBFragment.fragment_id.in_(fragment_ids)
            ).delete(synchronize_session=False)

            # 3. 最后删除Fragment
            fragment_deleted = db.query(Fragment).filter(
                Fragment.document_id == document_id
            ).delete()

            db.commit()

            self.logger.info(f"✅ 文档Fragment删除完成: {document_id} - Fragment: {fragment_deleted}个, KB关联: {kb_fragment_deleted}个, 索引条目: {index_deleted}个")
            return fragment_deleted

        except Exception as e:
            db.rollback()
            self.logger.error(f"❌ 删除文档Fragment失败: {document_id}, 错误: {e}")
            raise ProcessingError(f"删除文档Fragment失败: {str(e)}")

    def get_kb_fragments(
        self,
        db: Session,
        kb_id: str,
        fragment_type: Optional[FragmentType] = None,
        page: int = 1,
        page_size: int = 20
    ) -> FragmentListResponse:
        """获取知识库的Fragment列表"""
        try:
            # 构建查询 - 通过KBFragment关联表查询
            query = db.query(Fragment).join(KBFragment).filter(KBFragment.kb_id == kb_id)

            if fragment_type:
                query = query.filter(Fragment.fragment_type == fragment_type)

            # 获取总数
            total = query.count()

            # 分页查询
            fragments = query.offset((page - 1) * page_size).limit(page_size).all()

            return FragmentListResponse(
                fragments=[FragmentResponse.model_validate(f) for f in fragments],
                total=total,
                page=page,
                page_size=page_size
            )

        except Exception as e:
            self.logger.error(f"获取知识库Fragment列表失败: {kb_id}, 错误: {e}")
            raise ProcessingError(f"获取Fragment列表失败: {str(e)}")

    def get_document_fragments(
        self,
        db: Session,
        document_id: str,
        fragment_type: Optional[FragmentType] = None
    ) -> List[FragmentResponse]:
        """获取文档的所有Fragment"""
        try:
            query = db.query(Fragment).filter(Fragment.document_id == document_id)

            if fragment_type:
                query = query.filter(Fragment.fragment_type == fragment_type)

            fragments = query.all()
            return [FragmentResponse.model_validate(f) for f in fragments]

        except Exception as e:
            self.logger.error(f"获取文档Fragment失败: {document_id}, 错误: {e}")
            raise ProcessingError(f"获取文档Fragment失败: {str(e)}")

    def get_fragment_by_id(self, db: Session, fragment_id: str) -> Optional[Fragment]:
        """获取指定Fragment"""
        try:
            return db.query(Fragment).filter(Fragment.id == fragment_id).first()
        except Exception as e:
            self.logger.error(f"获取Fragment失败: {fragment_id}, 错误: {e}")
            raise ProcessingError(f"获取Fragment失败: {str(e)}")

    def update_fragment(
        self,
        db: Session,
        fragment_id: str,
        update_data: FragmentUpdate
    ) -> FragmentResponse:
        """更新Fragment"""
        try:
            fragment = db.query(Fragment).filter(Fragment.id == fragment_id).first()
            if not fragment:
                raise ValidationError(f"Fragment不存在: {fragment_id}")

            # 只允许更新meta_info
            if update_data.meta_info is not None:
                fragment.meta_info = update_data.meta_info

            db.commit()
            return FragmentResponse.model_validate(fragment)

        except Exception as e:
            db.rollback()
            self.logger.error(f"更新Fragment失败: {fragment_id}, 错误: {e}")
            raise ProcessingError(f"更新Fragment失败: {str(e)}")

    def get_document_fragment_stats(self, db: Session, document_id: str) -> Dict[str, int]:
        """获取文档Fragment统计信息"""
        try:
            # 获取文档的所有Fragment
            fragments = db.query(Fragment).filter(Fragment.document_id == document_id).all()

            # 统计各类型数量
            total_fragments = len(fragments)
            text_fragments = sum(1 for f in fragments if f.fragment_type == FragmentType.TEXT.value)
            screenshot_fragments = sum(1 for f in fragments if f.fragment_type == FragmentType.SCREENSHOT.value)
            figure_fragments = sum(1 for f in fragments if f.fragment_type == FragmentType.FIGURE.value)

            return {
                'total_fragments': total_fragments,
                'text_fragments': text_fragments,
                'screenshot_fragments': screenshot_fragments,
                'figure_fragments': figure_fragments
            }

        except Exception as e:
            self.logger.error(f"获取文档Fragment统计失败: {document_id}, 错误: {e}")
            raise ProcessingError(f"获取文档Fragment统计失败: {str(e)}")

    def get_kb_fragment_stats(self, db: Session, kb_id: str) -> FragmentStatsResponse:
        """获取知识库Fragment统计信息"""
        try:
            # 获取所有Fragment - 通过KBFragment关联表查询
            fragments = db.query(Fragment).join(KBFragment).filter(KBFragment.kb_id == kb_id).all()

            # 统计各类型数量
            total_fragments = len(fragments)
            text_fragments = sum(1 for f in fragments if f.fragment_type == FragmentType.TEXT.value)
            screenshot_fragments = sum(1 for f in fragments if f.fragment_type == FragmentType.SCREENSHOT.value)
            figure_fragments = sum(1 for f in fragments if f.fragment_type == FragmentType.FIGURE.value)

            # 获取最后更新时间
            last_updated = max(
                (f.updated_at for f in fragments if f.updated_at),
                default=None
            )

            return FragmentStatsResponse(
                kb_id=kb_id,
                total_fragments=total_fragments,
                text_fragments=text_fragments,
                screenshot_fragments=screenshot_fragments,
                figure_fragments=figure_fragments,
                activated_fragments=total_fragments,  # 简化处理，假设所有Fragment都是激活的
                last_updated=last_updated or datetime.now()
            )

        except Exception as e:
            self.logger.error(f"获取知识库Fragment统计失败: {kb_id}, 错误: {e}")
            raise ProcessingError(f"获取Fragment统计失败: {str(e)}")


# 全局服务实例
fragment_parser_service = FragmentParserService()