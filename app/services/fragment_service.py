"""
Fragment服务层
文件: fragment_service.py
创建时间: 2025-07-26
描述: 提供fragment管理和解析的业务逻辑
"""

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func, desc
from fastapi import HTTPException, status
from typing import List, Optional, Dict, Any, Tuple
import json
import logging
import time
from datetime import datetime

from app.models.fragment import Fragment, KBFragment
from app.models.document import Document, PhysicalDocument, KBDocument
from app.models.knowledge_base import KnowledgeBase
from app.schemas.fragment import (
    FragmentResponse, FragmentListResponse, FragmentUpdate,
    KBFragmentResponse, FragmentStatsResponse, FragmentType
)

logger = logging.getLogger(__name__)


class FragmentService:
    """Fragment服务类"""

    def __init__(self, db: Session):
        self.db = db

    def get_fragment_by_id(self, fragment_id: str) -> Optional[Fragment]:
        """根据ID获取Fragment"""
        return self.db.query(Fragment).filter(Fragment.id == fragment_id).first()

    def get_kb_fragments(
        self,
        kb_id: str,
        fragment_type: Optional[FragmentType] = None,
        page: int = 1,
        page_size: int = 20
    ) -> FragmentListResponse:
        """获取知识库的Fragment列表"""
        # 验证知识库存在
        kb = self.db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
        if not kb:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Knowledge base not found"
            )

        # 构建查询
        query = self.db.query(Fragment).join(
            KBFragment, Fragment.id == KBFragment.fragment_id
        ).filter(KBFragment.kb_id == kb_id)

        # 按类型过滤
        if fragment_type:
            query = query.filter(Fragment.fragment_type == fragment_type.value)

        # 获取总数
        total = query.count()

        # 分页查询
        offset = (page - 1) * page_size
        fragments = query.order_by(desc(Fragment.created_at)).offset(offset).limit(page_size).all()

        # 转换为响应模式
        fragment_responses = [
            FragmentResponse.model_validate(fragment) for fragment in fragments
        ]

        return FragmentListResponse(
            fragments=fragment_responses,
            total=total,
            page=page,
            page_size=page_size
        )

    def get_document_fragments(
        self,
        document_id: str,
        fragment_type: Optional[FragmentType] = None
    ) -> List[FragmentResponse]:
        """获取文档的所有Fragment"""
        # 验证文档存在
        document = self.db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )

        # 构建查询
        query = self.db.query(Fragment).filter(Fragment.document_id == document_id)

        # 按类型过滤
        if fragment_type:
            query = query.filter(Fragment.fragment_type == fragment_type.value)

        fragments = query.order_by(Fragment.fragment_index).all()

        return [FragmentResponse.model_validate(fragment) for fragment in fragments]

    def update_fragment(self, fragment_id: str, update_data: FragmentUpdate) -> FragmentResponse:
        """更新Fragment（仅允许有限修改）"""
        fragment = self.get_fragment_by_id(fragment_id)
        if not fragment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Fragment not found"
            )

        # 只允许修改meta_info
        if update_data.meta_info is not None:
            # 合并现有的meta_info
            current_meta = {}
            if fragment.meta_info:
                try:
                    current_meta = json.loads(fragment.meta_info) if isinstance(fragment.meta_info, str) else fragment.meta_info
                except (json.JSONDecodeError, TypeError):
                    current_meta = {}

            # 更新允许的字段
            current_meta.update(update_data.meta_info)
            fragment.meta_info = json.dumps(current_meta, ensure_ascii=False)

        try:
            self.db.commit()
            self.db.refresh(fragment)
            return FragmentResponse.model_validate(fragment)
        except Exception as e:
            self.db.rollback()
            logger.error(f"更新Fragment失败: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update fragment"
            )

    def get_kb_fragment_stats(self, kb_id: str) -> FragmentStatsResponse:
        """获取知识库Fragment统计信息"""
        # 验证知识库存在
        kb = self.db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
        if not kb:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Knowledge base not found"
            )

        # 统计各类型Fragment数量
        stats_query = self.db.query(
            Fragment.fragment_type,
            func.count(Fragment.id).label('count')
        ).join(
            KBFragment, Fragment.id == KBFragment.fragment_id
        ).filter(
            KBFragment.kb_id == kb_id
        ).group_by(Fragment.fragment_type)

        stats_result = stats_query.all()

        # 初始化统计数据
        total_fragments = 0
        text_fragments = 0
        screenshot_fragments = 0
        figure_fragments = 0

        for fragment_type, count in stats_result:
            total_fragments += count
            if fragment_type == FragmentType.TEXT.value:
                text_fragments = count
            elif fragment_type == FragmentType.SCREENSHOT.value:
                screenshot_fragments = count
            elif fragment_type == FragmentType.FIGURE.value:
                figure_fragments = count

        # 统计激活的Fragment数量
        activated_query = self.db.query(func.count(Fragment.id)).join(
            KBFragment, Fragment.id == KBFragment.fragment_id
        ).filter(
            KBFragment.kb_id == kb_id,
            Fragment.meta_info.like('%"activated": true%')
        )
        activated_fragments = activated_query.scalar() or 0

        return FragmentStatsResponse(
            kb_id=kb_id,
            total_fragments=total_fragments,
            text_fragments=text_fragments,
            screenshot_fragments=screenshot_fragments,
            figure_fragments=figure_fragments,
            activated_fragments=activated_fragments,
            last_updated=datetime.now()
        )

    def delete_document_fragments(self, document_id: str) -> bool:
        """删除文档的所有Fragment（内部使用）"""
        try:
            # 先删除KB关联
            self.db.query(KBFragment).filter(
                KBFragment.fragment_id.in_(
                    self.db.query(Fragment.id).filter(Fragment.document_id == document_id)
                )
            ).delete(synchronize_session=False)

            # 删除Fragment
            deleted_count = self.db.query(Fragment).filter(
                Fragment.document_id == document_id
            ).delete(synchronize_session=False)

            self.db.commit()
            logger.info(f"删除文档 {document_id} 的 {deleted_count} 个Fragment")
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"删除文档Fragment失败: {str(e)}")
            return False