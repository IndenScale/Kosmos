import re
import uuid
from typing import List, Dict, Tuple
from collections import deque

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload
from minio import Minio

from ...models import User, Document, KnowledgeSpaceMember
from ...schemas.reading import GrepRequest
from ...schemas.grep import (
    DocumentGrepResult, LineMatch, MultiGrepRequest, GrepSingleDocumentResponse
)
from ...utils.storage_utils import parse_storage_path

# TODO: Move these to a central configuration file (e.g., core/config.py)
GREP_MAX_DOCUMENTS_LIMIT = 1000
GREP_DEFAULT_MAX_MATCHES_PER_DOC = 100

class GrepService:
    def __init__(self, db: Session, minio: Minio):
        self.db = db
        self.minio = minio

    def _grep_single_document(self, document_id: uuid.UUID, req: GrepRequest) -> GrepSingleDocumentResponse:
        """
        Performs a regex search on a single document's canonical content.
        This is the core implementation of the grep logic.
        """
        doc = self.db.query(Document).options(
            joinedload(Document.canonical_content)
        ).filter(Document.id == document_id).first()
        
        if not doc or not doc.canonical_content:
            return GrepSingleDocumentResponse(matches=[], truncated=False)

        cc = doc.canonical_content
        try:
            bucket, object_name = parse_storage_path(cc.storage_path)
            response = self.minio.get_object(bucket, object_name)
            content_bytes = response.read()
            full_content = content_bytes.decode('utf-8')
        finally:
            response.close()
            response.release_conn()

        lines = full_content.splitlines()
        matches = []
        truncated = False
        
        flags = 0 if req.case_sensitive else re.IGNORECASE
        try:
            compiled_pattern = re.compile(req.pattern, flags)
        except re.error as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid regex pattern: {e}")

        context_buffer = deque(maxlen=req.context_lines_before)

        for i, line in enumerate(lines):
            if compiled_pattern.search(line):
                context_block = list(context_buffer)
                context_block.append(line)
                
                lookahead_end = min(len(lines), i + 1 + req.context_lines_after)
                for j in range(i + 1, lookahead_end):
                    context_block.append(lines[j])

                matches.append(LineMatch(
                    match_line_number=i + 1,
                    lines=context_block
                ))
                
                if req.max_matches and len(matches) >= req.max_matches:
                    truncated = True
                    break
            
            if req.context_lines_before > 0:
                context_buffer.append(line)
        
        return GrepSingleDocumentResponse(matches=matches, truncated=truncated)

    def get_search_scope_and_verify_access(
        self,
        knowledge_space_id: uuid.UUID | None,
        document_ids: List[uuid.UUID] | None,
        doc_ext: str | None,
        current_user: User
    ) -> List[uuid.UUID]:
        """
        Determines the list of document IDs to search, verifies user access,
        and enforces the maximum document limit.
        """
        doc_ids_to_search = []
        if knowledge_space_id:
            member = self.db.query(KnowledgeSpaceMember).filter(
                KnowledgeSpaceMember.knowledge_space_id == knowledge_space_id,
                KnowledgeSpaceMember.user_id == current_user.id
            ).first()
            if not member:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to knowledge space.")
            
            query = self.db.query(Document.id).filter(Document.knowledge_space_id == knowledge_space_id)
            if doc_ext:
                # Ensure the extension has a dot, but don't add one if it already exists
                if not doc_ext.startswith('.'):
                    doc_ext = '.' + doc_ext
                query = query.filter(Document.original_filename.endswith(doc_ext))

            doc_id_tuples = query.all()
            doc_ids_to_search = [doc_id for (doc_id,) in doc_id_tuples]

        elif document_ids:
            if not document_ids: return []
            
            required_ks_ids = {
                res[0] for res in self.db.query(Document.knowledge_space_id).filter(Document.id.in_(document_ids)).distinct().all()
            }
            accessible_ks_ids = {
                res[0] for res in self.db.query(KnowledgeSpaceMember.knowledge_space_id).filter(KnowledgeSpaceMember.user_id == current_user.id).all()
            }
            if not required_ks_ids.issubset(accessible_ks_ids):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to one or more documents.")
            
            query = self.db.query(Document.id).filter(Document.id.in_(document_ids))
            if doc_ext:
                if not doc_ext.startswith('.'):
                    doc_ext = '.' + doc_ext
                query = query.filter(Document.original_filename.endswith(doc_ext))
            
            doc_id_tuples = query.all()
            doc_ids_to_search = [doc_id for (doc_id,) in doc_id_tuples]
        
        if len(doc_ids_to_search) > GREP_MAX_DOCUMENTS_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Search scope exceeds the maximum limit of {GREP_MAX_DOCUMENTS_LIMIT} documents."
            )
        return doc_ids_to_search

    def perform_grep(
        self,
        doc_ids_to_search: List[uuid.UUID],
        request: MultiGrepRequest,
    ) -> Tuple[List[DocumentGrepResult], int, bool]:
        """
        Orchestrates the grep operation across multiple documents.
        """
        if not doc_ids_to_search:
            return [], 0, False

        all_results: List[DocumentGrepResult] = []
        total_matches = 0
        any_truncated = False

        doc_map = {
            doc.id: doc.original_filename for doc in 
            self.db.query(Document.id, Document.original_filename).filter(Document.id.in_(doc_ids_to_search)).all()
        }

        grep_req = GrepRequest(
            pattern=request.pattern, 
            case_sensitive=request.case_sensitive,
            max_matches=request.max_matches_per_doc or GREP_DEFAULT_MAX_MATCHES_PER_DOC,
            context_lines_before=request.context_lines_before,
            context_lines_after=request.context_lines_after
        )

        for doc_id in doc_ids_to_search:
            doc_name = doc_map.get(doc_id)
            if not doc_name: continue

            single_doc_result = self._grep_single_document(document_id=doc_id, req=grep_req)
            
            if single_doc_result.truncated:
                any_truncated = True
            
            if single_doc_result.matches:
                validated_matches = [LineMatch.model_validate(m) for m in single_doc_result.matches]
                all_results.append(DocumentGrepResult(
                    document_id=doc_id,
                    document_name=doc_name,
                    matches=validated_matches,
                    truncated=single_doc_result.truncated
                ))
                total_matches += len(validated_matches)
        
        return all_results, total_matches, any_truncated