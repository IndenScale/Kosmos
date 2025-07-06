from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from typing import List, Optional, Dict, Any
import json
import logging

from app.models.knowledge_base import KnowledgeBase, KBMember, KBRole
from app.models.user import User
from app.schemas.knowledge_base import KBCreate, KBUpdate, KBMemberAdd, TagDictionaryUpdate
from app.repositories.milvus_repo import MilvusRepository

# 配置日志
logger = logging.getLogger(__name__)

class KBService:
    def __init__(self, db: Session):
        self.db = db
        self.milvus_repo = MilvusRepository()

    def create_kb(self, kb_data: KBCreate, current_user: User) -> KnowledgeBase:
        """创建新知识库"""
        try:
            # 创建知识库
            db_kb = KnowledgeBase(
                name=kb_data.name,
                description=kb_data.description,
                owner_id=current_user.id,
                is_public=kb_data.is_public
            )
            self.db.add(db_kb)
            self.db.flush()  # 获取生成的ID

            # 添加拥有者为成员
            db_member = KBMember(
                kb_id=db_kb.id,
                user_id=current_user.id,
                role=KBRole.OWNER.value
            )
            self.db.add(db_member)
            self.db.commit()
            self.db.refresh(db_kb)
            return db_kb

        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create knowledge base"
            )

    def get_user_kbs(self, user_id: str) -> List[KnowledgeBase]:
        """获取用户参与的所有知识库"""
        return self.db.query(KnowledgeBase).join(KBMember).filter(
            KBMember.user_id == user_id
        ).all()

    def get_kb_by_id(self, kb_id: str) -> Optional[KnowledgeBase]:
        """根据ID获取知识库"""
        return self.db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()

    def update_kb(self, kb_id: str, kb_data: KBUpdate) -> KnowledgeBase:
        """更新知识库信息"""
        kb = self.get_kb_by_id(kb_id)
        if not kb:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Knowledge base not found"
            )

        update_data = kb_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(kb, field, value)

        self.db.commit()
        self.db.refresh(kb)
        return kb

    # def create_kb(self, name: str, description: str, owner_id: str, tag_dictionary: dict = None) -> KnowledgeBase:
    #     """创建知识库"""
    #     kb_id = str(uuid.uuid4())

    #     # 创建Milvus Collection
    #     collection_name = self.milvus_repo.create_collection(kb_id)

    #     kb = KnowledgeBase(
    #         id=kb_id,
    #         name=name,
    #         description=description,
    #         owner_id=owner_id,
    #         tag_dictionary=tag_dictionary or {},
    #         milvus_collection_id=collection_name
    #     )

    #     self.db.add(kb)
    #     self.db.commit()
    #     self.db.refresh(kb)

    #     # 创建所有者成员关系
    #     member = KBMember(
    #         kb_id=kb.id,
    #         user_id=owner_id,
    #         role=KBRole.OWNER.value
    #     )
    #     self.db.add(member)
    #     self.db.commit()

    #     return kb

    def delete_kb(self, kb_id: str) -> bool:
        """删除知识库"""
        kb = self.get_kb_by_id(kb_id)
        if not kb:
            return False

        # 删除Milvus Collection
        if kb.milvus_collection_id:
            self.milvus_repo.delete_collection(kb_id)

        # 删除SQLite记录
        self.db.delete(kb)
        self.db.commit()

        return True

    def get_kb_members(self, kb_id: str) -> List[KBMember]:
        """获取知识库成员列表"""
        return self.db.query(KBMember).filter(KBMember.kb_id == kb_id).all()

    def add_member(self, kb_id: str, member_data: KBMemberAdd) -> KBMember:
        """添加知识库成员"""
        # 检查用户是否存在
        user = self.db.query(User).filter(User.id == member_data.user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # 检查是否已经是成员
        existing_member = self.db.query(KBMember).filter(
            KBMember.kb_id == kb_id,
            KBMember.user_id == member_data.user_id
        ).first()

        if existing_member:
            # 更新角色
            existing_member.role = member_data.role.value
            self.db.commit()
            self.db.refresh(existing_member)
            return existing_member
        else:
            # 添加新成员
            new_member = KBMember(
                kb_id=kb_id,
                user_id=member_data.user_id,
                role=member_data.role.value
            )
            self.db.add(new_member)
            self.db.commit()
            self.db.refresh(new_member)
            return new_member

    def remove_member(self, kb_id: str, user_id: str) -> bool:
        """移除知识库成员"""
        member = self.db.query(KBMember).filter(
            KBMember.kb_id == kb_id,
            KBMember.user_id == user_id
        ).first()

        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found"
            )

        # 不能移除拥有者
        if member.role == KBRole.OWNER.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove knowledge base owner"
            )

        self.db.delete(member)
        self.db.commit()
        return True

    def update_tag_dictionary(self, kb_id: str, tag_data: TagDictionaryUpdate) -> KnowledgeBase:
        """更新标签字典"""
        from sqlalchemy import inspect
        from sqlalchemy.orm.attributes import flag_modified
        
        kb = self.get_kb_by_id(kb_id)
        if not kb:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Knowledge base not found"
            )

        logger.debug("更新前对象状态调试:")
        inspector = inspect(kb)
        logger.debug(f"   对象状态: {inspector.persistent}")
        logger.debug(f"   已修改字段: {inspector.modified}")
        logger.debug(f"   当前标签字典: {kb.tag_dictionary}")
        logger.debug(f"   当前字典大小: {len(str(kb.tag_dictionary)) if kb.tag_dictionary else 0} 字符")

        if tag_data.tag_dictionary:
            # 先保存旧字典用于比较
            old_dict = kb.tag_dictionary
            kb.tag_dictionary = tag_data.tag_dictionary
            
            # 强制标记字段为已修改
            flag_modified(kb, "tag_dictionary")
            
            logger.debug("字典更新对比:")
            logger.debug(f"   旧字典大小: {len(str(old_dict)) if old_dict else 0} 字符")
            logger.debug(f"   新字典大小: {len(str(kb.tag_dictionary)) if kb.tag_dictionary else 0} 字符")
            logger.debug(f"   字典是否相同: {old_dict == kb.tag_dictionary}")
            
        else:
            # TODO: 使用LLM生成标签字典
            # 这里暂时返回一个示例字典
            sample_dict = {
                "技术": {
                    "编程语言": ["Python", "JavaScript", "Java"],
                    "框架": ["FastAPI", "React", "Spring"]
                },
                "业务": {
                    "产品": ["需求分析", "产品设计"],
                    "运营": ["用户增长", "数据分析"]
                }
            }
            # 直接设置字典，让SQLAlchemy的类型转换器处理
            kb.tag_dictionary = sample_dict
            # 强制标记字段为已修改
            flag_modified(kb, "tag_dictionary")

        # 记录标签字典更新时间
        from datetime import datetime
        kb.last_tag_directory_update_time = datetime.now()
        
        logger.debug("更新后对象状态调试:")
        inspector = inspect(kb)
        logger.debug(f"   对象状态: {inspector.persistent}")
        logger.debug(f"   已修改字段: {inspector.modified}")
        logger.debug(f"   pending标识: {inspector.pending}")
        
        logger.info(f"更新标签字典: KB {kb_id}")
        logger.info(f"   新字典大小: {len(str(kb.tag_dictionary)) if kb.tag_dictionary else 0} 字符")
        logger.info(f"   更新时间: {kb.last_tag_directory_update_time}")

        try:
            logger.debug("执行数据库提交...")
            self.db.commit()
            logger.debug("数据库提交成功")
            
            logger.debug("刷新对象状态...")
            self.db.refresh(kb)
            logger.debug("对象状态刷新成功")
            
        except Exception as e:
            logger.error(f"数据库操作失败: {e}")
            self.db.rollback()
            raise e
        
        logger.info("标签字典已成功保存到数据库")
        
        # 验证更新结果
        logger.debug("最终验证:")
        logger.debug(f"   更新后字典大小: {len(str(kb.tag_dictionary)) if kb.tag_dictionary else 0} 字符")
        if kb.tag_dictionary and len(str(kb.tag_dictionary)) > 100:
            logger.debug(f"   字典前100字符: {str(kb.tag_dictionary)[:100]}...")
        
        return kb

    def get_outdated_documents(self, kb_id: str) -> List[dict]:
        """获取标签可能过时的文档列表"""
        from repositories.chunk_repo import ChunkRepository
        chunk_repo = ChunkRepository(self.db)

        outdated_chunks = chunk_repo.get_outdated_chunks(kb_id)

        # 按文档分组统计
        doc_stats = {}
        for chunk in outdated_chunks:
            if chunk.document_id not in doc_stats:
                doc_stats[chunk.document_id] = {
                    'document_id': chunk.document_id,
                    'outdated_chunk_count': 0
                }
            doc_stats[chunk.document_id]['outdated_chunk_count'] += 1

        return list(doc_stats.values())

    def get_member_role(self, kb_id: str, user_id: str) -> Optional[str]:
        """获取用户在知识库中的角色"""
        member = self.db.query(KBMember).filter(
            KBMember.kb_id == kb_id,
            KBMember.user_id == user_id
        ).first()
        return member.role if member else None

    def get_kb_stats(self, kb_id: str) -> dict:
        """获取知识库统计信息"""
        kb = self.get_kb_by_id(kb_id)
        if not kb:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Knowledge base not found"
            )

        # 通过DocumentService获取统计信息
        from app.services.document_service import DocumentService
        doc_service = DocumentService(self.db)

        document_count = doc_service.get_kb_document_count(kb_id)
        chunk_count = doc_service.get_kb_chunk_count(kb_id)

        return {
            "document_count": document_count,
            "chunk_count": chunk_count,
            "tag_dictionary": kb.tag_dictionary if kb.tag_dictionary else {}
        }