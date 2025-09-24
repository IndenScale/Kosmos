import uuid
from typing import List, Optional, Any
from pydantic import BaseModel, Field, field_validator

class SearchFunnel(BaseModel):
    vector_recalled: int
    keyword_recalled: int
    combined_recalled: int
    filtered: int
    final_aggregated: int

class ScoreBreakdown(BaseModel):
    vector_score: float
    keyword_score: float
    booster_multiplier: float
    final_score: float

class SearchResultItem(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_filename: str
    content: str
    unshown_char_count: int
    score: float
    scores_breakdown: Optional[ScoreBreakdown] = None
    tags: Optional[List[str]] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None

    @field_validator('chunk_id', 'document_id', mode='before', check_fields=False)
    @classmethod
    def uuid_from_bytes(cls, v):
        if isinstance(v, bytes):
            return uuid.UUID(bytes=v)
        return v

class SearchFilters(BaseModel):
    # DEPRECATED in favor of document_ids_include
    document_id: Optional[uuid.UUID] = None
    
    document_ids_include: Optional[List[uuid.UUID]] = Field(default=None, description="List of document IDs to exclusively search within.")
    document_ids_exclude: Optional[List[uuid.UUID]] = Field(default=None, description="List of document IDs to exclude from the search.")
    
    filename_contains: Optional[str] = Field(default=None, description="A substring to match within the document's filename (case-insensitive).")
    filename_does_not_contain: Optional[str] = Field(default=None, description="A substring to exclude from the document's filename (case-insensitive).")
    extensions_include: Optional[List[str]] = Field(default=None, description="A list of file extensions to include (e.g., ['pdf', 'docx']). Case-insensitive.")
    extensions_exclude: Optional[List[str]] = Field(default=None, description="A list of file extensions to exclude (e.g., ['txt', 'log']). Case-insensitive.")

    tags: Optional[List[str]] = None
    keywords_include_all: Optional[List[str]] = Field(
        default=None, 
        description="A list of keywords that MUST ALL be present in the chunk's content (AND logic)."
    )
    keywords_exclude_any: Optional[List[str]] = Field(
        default=None,
        description="A list of keywords where if ANY are present, the chunk is excluded (NOT (A OR B))."
    )
    
    # DEPRECATED in favor of keywords_include_all
    keywords: Optional[List[str]] = Field(
        default=None, 
        description="[DEPRECATED] Use keywords_include_all instead."
    )

    @field_validator(
        'document_id', 'document_ids_include', 'document_ids_exclude',
        mode='before', check_fields=False
    )
    @classmethod
    def uuid_from_bytes(cls, v):
        if isinstance(v, bytes):
            return uuid.UUID(bytes=v)
        if isinstance(v, list):
            return [uuid.UUID(bytes=i) if isinstance(i, bytes) else i for i in v]
        return v

class SearchRequest(BaseModel):
    query: str
    knowledge_space_id: uuid.UUID
    top_k: int = 10
    filters: Optional[SearchFilters] = None
    boosters: Optional[List[str]] = None
    max_content_length: int = 500
    detailed: bool = False

    @field_validator('knowledge_space_id', mode='before', check_fields=False)
    @classmethod
    def uuid_from_bytes(cls, v):
        if isinstance(v, bytes):
            return uuid.UUID(bytes=v)
        return v

class SearchResponse(BaseModel):
    results: List[SearchResultItem]
    suggested_tags: List[str] = []
    search_funnel: Optional[SearchFunnel] = None