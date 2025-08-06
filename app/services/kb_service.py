from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from typing import List, Optional, Dict, Any
import json
import logging

from app.models.knowledge_base import KnowledgeBase, KBMember, KBRole
from app.models.user import User
from app.models.credential import KBModelConfig
from app.schemas.knowledge_base import KBCreate, KBUpdate, KBMemberAdd, TagDictionaryUpdate
from app.schemas.credential import KBModelConfigCreate
from app.repositories.milvus_repo import MilvusRepository
from app.services.config_service import config_service
from app.services.credential_service import credential_service

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
            
            # 自动配置功能
            self._auto_configure_kb(db_kb, current_user)
            
            self.db.commit()
            self.db.refresh(db_kb)
            return db_kb

        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create knowledge base"
            )
        except Exception as e:
            self.db.rollback()
            logger.error(f"创建知识库时发生错误: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create knowledge base: {str(e)}"
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
        from app.models.fragment import KBFragment
        from app.models.document import KBDocument
        from app.models.index import Index
        from app.models.job import Job, Task
        from app.models.credential import KBModelConfig
        
        kb = self.get_kb_by_id(kb_id)
        if not kb:
            return False

        try:
            # 1. 删除Milvus Collection
            if kb.milvus_collection_id:
                self.milvus_repo.delete_collection(kb_id)

            # 2. 删除知识库相关的所有外键引用
            # 首先获取所有相关的job_ids
            job_ids = [job.id for job in self.db.query(Job).filter(Job.kb_id == kb_id).all()]
            
            # 删除tasks（必须在删除jobs之前）
            if job_ids:
                self.db.query(Task).filter(Task.job_id.in_(job_ids)).delete(synchronize_session=False)
            
            # 删除任务记录
            self.db.query(Job).filter(Job.kb_id == kb_id).delete()
            
            # 删除 kb_fragments 关联
            self.db.query(KBFragment).filter(KBFragment.kb_id == kb_id).delete()
            
            # 删除 kb_documents 关联
            self.db.query(KBDocument).filter(KBDocument.kb_id == kb_id).delete()
            
            # 删除索引记录
            self.db.query(Index).filter(Index.kb_id == kb_id).delete()
            
            # 删除知识库模型配置
            self.db.query(KBModelConfig).filter(KBModelConfig.kb_id == kb_id).delete()

            # 3. 删除知识库记录（成员关联会通过cascade自动删除）
            self.db.delete(kb)
            self.db.commit()

            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"删除知识库失败: kb_id={kb_id}, 错误: {e}")
            raise e

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
            logger.error(f"获取知识库模型配置失败: {e}")
            return {
                "kb": kb,
                "model_configs": None
            }
    
    def _auto_configure_kb(self, kb: KnowledgeBase, user: User) -> None:
        """自动配置知识库"""
        try:
            # 检查是否启用自动配置
            if not config_service.should_auto_configure(user.id):
                logger.info(f"用户 {user.id} 未启用自动配置")
                return
            
            logger.info(f"开始为知识库 {kb.id} 自动配置")
            
            # 获取系统配置
            system_config = config_service.get_system_config(user.id)
            overwrite_existing = system_config.get('overwrite_existing', False)
            
            # 1. 自动设置标签字典
            if system_config.get('auto_set_tags', False):
                self._auto_set_tag_dictionary(kb, user.id)
            
            # 2. 自动创建模型凭证和配置
            if system_config.get('auto_create_models', False):
                self._auto_create_model_configs(kb, user.id, overwrite_existing)
                
        except Exception as e:
            logger.error(f"自动配置知识库 {kb.id} 失败: {e}")
            # 不抛出异常，避免影响知识库创建
    
    def _auto_set_tag_dictionary(self, kb: KnowledgeBase, user_id: str) -> None:
        """自动设置标签字典"""
        try:
            default_tags = config_service.get_default_tag_dictionary(user_id)
            if default_tags:
                kb.tag_dictionary = json.dumps(default_tags, ensure_ascii=False)
                logger.info(f"为知识库 {kb.id} 设置默认标签字典")
            else:
                logger.warning(f"用户 {user_id} 没有配置默认标签字典")
        except Exception as e:
            logger.error(f"设置标签字典失败: {e}")
    
    def _auto_create_model_configs(self, kb: KnowledgeBase, user_id: str, overwrite_existing: bool) -> None:
        """自动创建模型配置"""
        try:
            # 创建凭证
            credential_id_map = config_service.create_credentials_from_config(
                self.db, user_id, overwrite_existing
            )
            
            if not credential_id_map:
                logger.warning(f"用户 {user_id} 没有有效的模型配置")
                return
            
            # 获取模型配置
            models_config = config_service.get_model_configs(user_id)
            
            # 构建KBModelConfig数据
            config_data = {
                'kb_id': kb.id
            }
            
            # 设置各类型模型配置
            for model_key, credential_id in credential_id_map.items():
                model_config = models_config.get(model_key, {})
                model_name = model_config.get('model_name', '')
                config_params = config_service.get_model_config_params(user_id, model_key)
                
                if model_key == 'embedding':
                    config_data['embedding_model_name'] = model_name
                    config_data['embedding_credential_id'] = credential_id
                    config_data['embedding_config_params'] = config_params
                elif model_key == 'reranker':
                    config_data['reranker_model_name'] = model_name
                    config_data['reranker_credential_id'] = credential_id
                    config_data['reranker_config_params'] = config_params
                elif model_key == 'llm':
                    config_data['llm_model_name'] = model_name
                    config_data['llm_credential_id'] = credential_id
                    config_data['llm_config_params'] = config_params
                elif model_key == 'vlm':
                    config_data['vlm_model_name'] = model_name
                    config_data['vlm_credential_id'] = credential_id
                    config_data['vlm_config_params'] = config_params
            
            # 创建KBModelConfig
            kb_model_config = KBModelConfig(**config_data)
            self.db.add(kb_model_config)
            
            logger.info(f"为知识库 {kb.id} 创建模型配置，包含 {len(credential_id_map)} 个模型")
             
        except Exception as e:
            logger.error(f"创建模型配置失败: {e}")
            # 不抛出异常，避免影响知识库创建