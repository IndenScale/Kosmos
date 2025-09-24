"""
Recallers are responsible for the first stage of search: retrieving a broad set of
candidate chunks from different sources (vector DB, keyword index, etc.).
"""
import uuid
from typing import List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import text

from ..vector_db_service_v2 import VectorDBServiceV2

class Recallers:
    def __init__(self, db: Session):
        self.db = db
        self.vector_db = VectorDBServiceV2()

    def vector_recall(self, knowledge_space_id: uuid.UUID, query_vector: List[float], top_k: int, embedding_dim: int) -> List[Dict]:
        """
        Performs semantic search using the vector database.
        Returns a list of dicts with 'chunk_id' and a relevance 'score'.
        """
        try:
            # The search method returns a list of dicts with 'chunk_id' and 'score' (distance)
            results = self.vector_db.search(
                knowledge_space_id=str(knowledge_space_id),
                query_vector=query_vector,
                top_k=top_k,
                embedding_dim=embedding_dim
            )
            
            processed_results = []
            for r in results:
                # Convert distance to a similarity score (higher is better)
                # This simple formula works well for L2 distance.
                similarity = 1.0 / (1.0 + r['score'])
                processed_results.append({
                    'chunk_id': str(r['chunk_id']),
                    'score': similarity
                })
            return processed_results
        except Exception as e:
            print(f"Error during vector recall: {e}")
            return []

    def keyword_recall(self, query: str, knowledge_space_id: uuid.UUID, top_k: int, document_id: uuid.UUID | None = None) -> List[Dict]:
        """
        Performs keyword search using the SQLite FTS5 virtual table, scoped to the
        correct knowledge space and optional document.
        """
        sanitized_query = f'"{query.replace('"', '""')}"'

        # Join FTS -> chunks -> documents to filter by knowledge_space_id and document_id
        sql_query_str = """
            SELECT
                c.id AS chunk_id,
                fts.rank
            FROM chunks_fts AS fts
            JOIN chunks AS c ON fts.rowid = c.rowid
            JOIN documents AS d ON c.document_id = d.id
            WHERE
                fts.chunks_fts MATCH :query
                AND d.knowledge_space_id = :knowledge_space_id
        """
        
        params = {
            "query": sanitized_query,
            "knowledge_space_id": str(knowledge_space_id)
        }

        if document_id:
            sql_query_str += " AND d.id = :document_id"
            params["document_id"] = str(document_id)

        sql_query_str += " ORDER BY rank LIMIT :limit;"
        params["limit"] = top_k
        
        sql_query = text(sql_query_str)
        
        try:
            results = self.db.execute(sql_query, params).fetchall()
            
            return [
                {"chunk_id": str(row.chunk_id), "score": 1.0 / (1.0 - row.rank)}
                for row in results
            ]
        except Exception as e:
            print(f"Error during keyword recall: {e}")
            return []