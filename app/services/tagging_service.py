from sqlalchemy.orm import Session
from typing import List, Dict, Any
import json

from app.models.chunk import Chunk
from app.models.knowledge_base import KnowledgeBase
from app.repositories.chunk_repo import ChunkRepository
from app.repositories.milvus_repo import MilvusRepository
from app.utils.ai_utils import AIUtils


class TaggingService:
    """独立的标签生成服务
    
    负责为已摄入的chunks生成标签，可以被SDTM替代
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.ai_utils = AIUtils()
        self.chunk_repo = ChunkRepository(db)
        self.milvus_repo = MilvusRepository()
    
    def tag_chunks(self, kb_id: str, chunk_ids: List[str] = None) -> Dict[str, Any]:
        """为指定的chunks生成标签
        
        Args:
            kb_id: 知识库ID
            chunk_ids: 要处理的chunk ID列表，如果为None则处理所有无标签的chunks
            
        Returns:
            Dict包含处理结果
        """
        try:
            # 获取知识库信息
            kb = self.db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
            if not kb:
                raise ValueError(f"知识库 {kb_id} 不存在")
            
            tag_dictionary = kb.tag_dictionary or {}
            
            # 获取要处理的chunks
            if chunk_ids:
                chunks = self.chunk_repo.get_chunks_by_ids(chunk_ids)
            else:
                chunks = self.chunk_repo.get_untagged_chunks(kb_id)
            
            if not chunks:
                return {
                    "success": True,
                    "message": "没有需要处理的chunks",
                    "processed_count": 0,
                    "failed_count": 0
                }
            
            processed_count = 0
            failed_count = 0
            
            for chunk in chunks:
                try:
                    # 生成标签
                    tags = self.ai_utils.get_tags(chunk.content, tag_dictionary)
                    
                    # 更新chunk的标签
                    chunk.tags = json.dumps(tags, ensure_ascii=False)
                    
                    # 同步更新Milvus中的标签
                    try:
                        vector_exists = self.milvus_repo.check_vector_exists(chunk.kb_id, chunk.id)
                        if vector_exists:
                            self.milvus_repo.update_vector_metadata(
                                kb_id=chunk.kb_id,
                                chunk_id=chunk.id,
                                metadata={"tags": tags}
                            )
                    except Exception as milvus_error:
                        print(f"更新Milvus标签失败: {milvus_error}")
                        # Milvus更新失败不应阻止SQLite更新
                    
                    processed_count += 1
                    
                except Exception as e:
                    print(f"处理chunk {chunk.id} 失败: {e}")
                    failed_count += 1
                    continue
            
            # 提交数据库更改
            self.db.commit()
            
            return {
                "success": True,
                "message": f"标签生成完成：成功 {processed_count} 个，失败 {failed_count} 个",
                "processed_count": processed_count,
                "failed_count": failed_count
            }
            
        except Exception as e:
            self.db.rollback()
            return {
                "success": False,
                "message": f"标签生成失败: {str(e)}",
                "processed_count": 0,
                "failed_count": 0
            }
    
    def batch_tag_document(self, kb_id: str, document_id: str) -> Dict[str, Any]:
        """为指定文档的所有chunks生成标签"""
        try:
            # 获取文档的所有chunks
            chunks = self.chunk_repo.get_chunks_by_document(document_id)
            chunk_ids = [chunk.id for chunk in chunks]
            
            return self.tag_chunks(kb_id, chunk_ids)
            
        except Exception as e:
            return {
                "success": False,
                "message": f"批量标注文档失败: {str(e)}",
                "processed_count": 0,
                "failed_count": 0
            }
    
    def get_tagging_stats(self, kb_id: str) -> Dict[str, Any]:
        """获取知识库的标注统计信息"""
        try:
            all_chunks = self.chunk_repo.get_chunks_by_kb(kb_id)
            
            total_chunks = len(all_chunks)
            tagged_chunks = 0
            untagged_chunks = 0
            
            for chunk in all_chunks:
                if chunk.tags:
                    try:
                        tags = json.loads(chunk.tags) if isinstance(chunk.tags, str) else chunk.tags
                        if tags and len(tags) > 0:
                            tagged_chunks += 1
                        else:
                            untagged_chunks += 1
                    except (json.JSONDecodeError, TypeError):
                        untagged_chunks += 1
                else:
                    untagged_chunks += 1
            
            return {
                "total_chunks": total_chunks,
                "tagged_chunks": tagged_chunks,
                "untagged_chunks": untagged_chunks,
                "tagging_progress": (tagged_chunks / total_chunks * 100) if total_chunks > 0 else 0
            }
            
        except Exception as e:
            return {
                "total_chunks": 0,
                "tagged_chunks": 0,
                "untagged_chunks": 0,
                "tagging_progress": 0,
                "error": str(e)
            } 