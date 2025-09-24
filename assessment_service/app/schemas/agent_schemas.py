"""
Pydantic schemas for Agent Actions.
"""
from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID

class SearchActionRequest(BaseModel):
    query: str
    top_k: int = 5
    
    # Document Filters
    doc_ids_include: Optional[List[str]] = None
    doc_ids_exclude: Optional[List[str]] = None
    filename_contains: Optional[str] = None
    filename_does_not_contain: Optional[str] = None
    extensions_include: Optional[List[str]] = None
    extensions_exclude: Optional[List[str]] = None
    
    # Content Filters
    keywords_include_all: Optional[List[str]] = None
    keywords_exclude_any: Optional[List[str]] = None
    
    # Result Tuning
    boosters: Optional[List[str]] = None

class ReadActionRequest(BaseModel):
    doc_ref: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None

class GrepActionRequest(BaseModel):
    pattern: str
    doc_id: str
    context: int = 0
    ignore_case: bool = False
    max_count: Optional[int] = None

class GrepScope(BaseModel):
    document_ids: Optional[List[UUID]] = None
    knowledge_space_id: Optional[UUID] = None

class MultiGrepActionRequest(BaseModel):
    pattern: str
    scope: GrepScope
    case_sensitive: bool = False
    max_matches_per_doc: Optional[int] = None
    context_lines_before: int = 0
    context_lines_after: int = 0