from sqlalchemy.orm import Session
from models.chunk import Chunk
from typing import List, Optional
import json

class ChunkRepository:
    """Chunk数据访问层"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_chunk_by_id(self, chunk_id: str) -> Optional[Chunk]:
        """根据ID获取chunk"""
        return self.db.query(Chunk).filter(Chunk.id == chunk_id).first()
    
    def get_chunks_by_document(self, document_id: str) -> List[Chunk]:
        """获取文档的所有chunks"""
        return self.db.query(Chunk).filter(Chunk.document_id == document_id).order_by(Chunk.chunk_index).all()
    
    def get_chunks_by_kb(self, kb_id: str, limit: int = None) -> List[Chunk]:
        """获取知识库的所有chunks"""
        query = self.db.query(Chunk).filter(Chunk.kb_id == kb_id)
        if limit:
            query = query.limit(limit)
        return query.all()
    
    def create_chunk(self, chunk: Chunk) -> Chunk:
        """创建新chunk"""
        self.db.add(chunk)
        self.db.commit()
        self.db.refresh(chunk)
        return chunk
    
    def delete_chunks_by_document(self, document_id: str):
        """删除文档的所有chunks"""
        self.db.query(Chunk).filter(Chunk.document_id == document_id).delete()
        self.db.commit()