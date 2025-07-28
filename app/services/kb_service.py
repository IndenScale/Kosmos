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
        from sqlalchemy.orm.attributes import flag_modified
        from datetime import datetime
        
        kb = self.get_kb_by_id(kb_id)
        if not kb:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Knowledge base not found"
            )

        # 直接更新标签字典
        kb.tag_dictionary = tag_data.tag_dictionary
        
        # 强制标记字段为已修改
        flag_modified(kb, "tag_dictionary")
        
        # 记录标签字典更新时间
        kb.last_tag_dictionary_update_time = datetime.now()
        
        logger.info(f"更新标签字典: KB {kb_id}")
        
        try:
            self.db.commit()
            self.db.refresh(kb)
        except Exception as e:
            logger.error(f"数据库操作失败: {e}")
            self.db.rollback()
            raise e
        
        logger.info("标签字典已成功保存到数据库")
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

    def get_kb_with_model_configs(self, kb_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """获取知识库详情，包含模型配置信息"""
        from app.services.credential_service import credential_service
        from app.schemas.credential import CredentialResponse, KBModelConfigResponse, KBModelConfigsResponse
        
        kb = self.get_kb_by_id(kb_id)
        if not kb:
            return None
        
        # 检查用户权限
        member_role = self.get_member_role(kb_id, user_id)
        if not member_role:
            return None
        
        try:
            # 获取模型配置
            configs = credential_service.get_kb_model_configs(
                db=self.db,
                kb_id=kb_id,
                user_id=user_id
            )
            
            # 构造配置响应
            config_responses = []
            for config in configs:
                # 使用credential_service的智能方法获取配置响应
                config_response = credential_service.get_kb_model_config_response(
                    db=self.db,
                    config=config,
                    user_id=user_id
                )
                config_responses.append(config_response)
            
            model_configs = KBModelConfigsResponse(
                kb_id=kb_id,
                configs=config_responses
            )
            
            return {
                "kb": kb,
                "model_configs": model_configs
            }
            
        except Exception as e:
            logger.warning(f"获取知识库 {kb_id} 的模型配置失败: {e}")
            return {
                "kb": kb,
                "model_configs": None
            }