# from sqlalchemy.orm import Session
# from app.models.chunk import Chunk
# from typing import List, Optional
# import json

# class ChunkRepository:
#     """Chunk数据访问层"""

#     def __init__(self, db: Session):
#         self.db = db

#     def get_chunk_by_id(self, chunk_id: str) -> Optional[Chunk]:
#         """根据ID获取chunk"""
#         return self.db.query(Chunk).filter(Chunk.id == chunk_id).first()

#     def get_chunks_by_document(self, document_id: str) -> List[Chunk]:
#         """获取文档的所有chunks"""
#         return self.db.query(Chunk).filter(Chunk.document_id == document_id).order_by(Chunk.chunk_index).all()

#     def get_chunks_by_kb(self, kb_id: str, limit: int = None) -> List[Chunk]:
#         """获取知识库的所有chunks"""
#         query = self.db.query(Chunk).filter(Chunk.kb_id == kb_id)
#         if limit:
#             query = query.limit(limit)
#         return query.all()

#     def create_chunk(self, chunk: Chunk) -> Chunk:
#         """创建新chunk"""
#         self.db.add(chunk)
#         self.db.commit()
#         self.db.refresh(chunk)
#         return chunk

#     def delete_chunks_by_document(self, document_id: str):
#         """删除文档的所有chunks"""
#         self.db.query(Chunk).filter(Chunk.document_id == document_id).delete()
#         self.db.commit()

#     def delete_chunks_by_kb_and_document(self, kb_id: str, document_id: str):
#         """删除特定知识库中特定文档的所有chunks"""
#         self.db.query(Chunk).filter(
#             Chunk.kb_id == kb_id,
#             Chunk.document_id == document_id
#         ).delete()
#         self.db.commit()

#     def get_outdated_chunks(self, kb_id: str) -> List[Chunk]:
#         """获取标签可能过时的chunks"""
#         from app.models.knowledge_base import KnowledgeBase
#         from app.models.document import KBDocument

#         # 获取知识库的标签字典最后更新时间
#         kb = self.db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
#         if not kb or not kb.last_tag_directory_update_time:
#             return []

#         # 查找摄入时间早于标签字典更新时间的chunks
#         outdated_chunks = self.db.query(Chunk).join(
#             KBDocument, Chunk.document_id == KBDocument.document_id
#         ).filter(
#             Chunk.kb_id == kb_id,
#             KBDocument.kb_id == kb_id,
#             KBDocument.last_ingest_time < kb.last_tag_directory_update_time
#         ).all()

#         return outdated_chunks

#     def get_kb_chunk_count(self, kb_id: str) -> int:
#         """获取知识库chunk数量"""
#         return self.db.query(Chunk).filter(Chunk.kb_id == kb_id).count()

#     def get_chunks_by_ids(self, chunk_ids: List[str]) -> List[Chunk]:
#         """根据ID列表获取chunks"""
#         return self.db.query(Chunk).filter(Chunk.id.in_(chunk_ids)).all()

#     def get_untagged_chunks(self, kb_id: str) -> List[Chunk]:
#         """获取没有标签的chunks"""
#         chunks = self.db.query(Chunk).filter(Chunk.kb_id == kb_id).all()

#         untagged_chunks = []
#         for chunk in chunks:
#             if not chunk.tags:
#                 untagged_chunks.append(chunk)
#             else:
#                 try:
#                     tags = json.loads(chunk.tags) if isinstance(chunk.tags, str) else chunk.tags
#                     if not tags or len(tags) == 0:
#                         untagged_chunks.append(chunk)
#                 except (json.JSONDecodeError, TypeError):
#                     untagged_chunks.append(chunk)

#         return untagged_chunks