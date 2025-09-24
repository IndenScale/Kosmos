import re
import uuid
import logging
from typing import Union, List, Dict, Any
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, status
from minio import Minio

from ...models import Document, CanonicalContent, Asset, DocumentAssetContext, ContentPageMapping
from ...core.config import settings
from ...utils.storage_utils import parse_storage_path

logger = logging.getLogger(__name__)

class ReadService:
    def __init__(self, db: Session, minio: Minio):
        self.db = db
        self.minio = minio

    def _resolve_location_to_line_index(self, location: Union[int, float], total_lines: int, clamp: bool = False) -> int:
        """
        Resolves a user-provided location (line number or percentage) to a 0-based line index.
        """
        if isinstance(location, float):
            if not 0.0 <= location <= 1.0:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Percentage must be between 0.0 and 1.0.")
            line_index = int(location * total_lines)
        elif isinstance(location, int):
            line_index = location - 1
        else:
            raise NotImplementedError("Title-based location is not yet supported.")

        if clamp:
            return max(0, min(line_index, total_lines - 1))
        else:
            if not 0 <= line_index < total_lines:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Start line {location} is out of document bounds (1-{total_lines}).")
            return line_index

    def _get_assets_in_content(self, content: str, document_id: uuid.UUID) -> List[Dict[str, Any]]:
        """
        Gets the assets referenced in a piece of content and their analysis results.
        """
        asset_uris = re.findall(r'(asset://[\w-]+)', content)
        if not asset_uris:
            return []

        asset_ids_str = {uri.replace('asset://', '') for uri in asset_uris}
        if not asset_ids_str:
            return []
        
        asset_ids_uuid = {uuid.UUID(id_str) for id_str in asset_ids_str}

        contexts = self.db.query(DocumentAssetContext).options(
            joinedload(DocumentAssetContext.asset)
        ).filter(
            DocumentAssetContext.document_id == document_id,
            DocumentAssetContext.asset_id.in_(asset_ids_uuid)
        ).all()

        assets_in_content = []
        for context in contexts:
            asset = context.asset
            if not asset: continue

            assets_in_content.append({
                "asset_id": asset.id,
                "asset_type": asset.asset_type,
                "description": context.analysis_result
            })

        return assets_in_content

    def read_document_content(
        self, 
        document_id: uuid.UUID,
        start: Union[int, float] = 1,
        end: Union[int, float, None] = None,
        max_lines: int = 200,
        max_chars: int = 8000,
        preserve_integrity: bool = True
    ) -> dict:
        """
        Reads a specific portion of a document's canonical content with rich features, including page numbers.
        """
        doc = self.db.query(Document).options(
            joinedload(Document.canonical_content)
        ).filter(Document.id == document_id).first()
        
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
        if not doc.canonical_content:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document does not have canonical content yet.")

        cc = doc.canonical_content
        canonical_content_id = cc.id

        try:
            bucket, object_name = parse_storage_path(cc.storage_path)
            response = self.minio.get_object(bucket, object_name)
            content_bytes = response.read()
            full_content = content_bytes.decode('utf-8')
        finally:
            response.close()
            response.release_conn()

        lines = full_content.splitlines()
        total_lines = len(lines)
        if total_lines == 0:
            return {
                "char_count": 0,
                "lines": [], 
                "start_line": 0, 
                "end_line": 0, 
                "total_lines": 0, 
                "assets": [],
                "relevant_page_numbers": []
            }

        start_index = self._resolve_location_to_line_index(start, total_lines, clamp=False)
        end_index = self._resolve_location_to_line_index(end, total_lines, clamp=True) if end is not None else total_lines - 1

        if start_index > end_index:
            return {
                "char_count": 0,
                "lines": [], 
                "start_line": start_index + 1, 
                "end_line": start_index + 1, 
                "total_lines": total_lines, 
                "assets": [],
                "relevant_page_numbers": []
            }

        # Fetch page mappings for the requested line range
        page_mappings = self.db.query(ContentPageMapping).filter(
            ContentPageMapping.canonical_content_id == canonical_content_id,
            ContentPageMapping.line_from <= end_index + 1,
            ContentPageMapping.line_to >= start_index + 1
        ).order_by(ContentPageMapping.line_from).all()

        # Create a lookup map for faster access
        line_to_page_map = {}
        for mapping in page_mappings:
            for line_num in range(mapping.line_from, mapping.line_to + 1):
                line_to_page_map[line_num] = mapping.page_number

        selected_lines = lines[start_index : end_index + 1]

        final_lines_with_meta = []
        current_chars = 0
        is_truncated = False

        for i, line_content in enumerate(selected_lines):
            current_line_num = start_index + i + 1
            if i >= max_lines:
                is_truncated = True
                break

            line_len_with_newline = len(line_content) + 1
            if current_chars + line_len_with_newline > max_chars:
                is_truncated = True
                if preserve_integrity:
                    if not final_lines_with_meta:
                        final_lines_with_meta.append({
                            "line": current_line_num,
                            "page": line_to_page_map.get(current_line_num),
                            "content": line_content[:max_chars]
                        })
                    break
                else:
                    remaining_chars = max_chars - current_chars
                    final_lines_with_meta.append({
                        "line": current_line_num,
                        "page": line_to_page_map.get(current_line_num),
                        "content": line_content[:remaining_chars]
                    })
                    break
            
            final_lines_with_meta.append({
                "line": current_line_num,
                "page": line_to_page_map.get(current_line_num),
                "content": line_content
            })
            current_chars += line_len_with_newline

        result_content_str = "\n".join([line['content'] for line in final_lines_with_meta])
        if is_truncated:
             result_content_str += "\n[...]"

        # Aggregate the unique page numbers from the final lines
        relevant_pages = sorted(list(set(
            line['page'] for line in final_lines_with_meta if line.get('page') is not None
        )))

        # The primary content is now the detailed line list
        result_content_str = "\n".join([line['content'] for line in final_lines_with_meta])
        assets = self._get_assets_in_content(result_content_str, document_id)

        return {
            "char_count": len(result_content_str),
            "start_line": start_index + 1,
            "end_line": start_index + len(final_lines_with_meta),
            "total_lines": total_lines,
            "assets": assets,
            "lines": final_lines_with_meta,
            "relevant_page_numbers": relevant_pages
        }