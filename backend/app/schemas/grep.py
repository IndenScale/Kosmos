import uuid
from typing import List, Optional
from pydantic import BaseModel, Field, root_validator, field_validator

# --- Core Data Structures for Grep ---

class LineMatch(BaseModel):
    """Represents a single regex match and its surrounding context lines."""
    match_line_number: int
    lines: List[str]

class GrepSingleDocumentResponse(BaseModel):
    """Internal DTO for the result of grepping a single document."""
    matches: List[LineMatch]
    truncated: bool = Field(description="Indicates if the search was stopped because max_matches was reached.")

# --- API-Facing Schemas ---

class GrepScope(BaseModel):
    document_ids: Optional[List[uuid.UUID]] = Field(None, description="A list of document IDs to search within.")
    knowledge_space_id: Optional[uuid.UUID] = Field(None, description="A knowledge space ID to search all its documents.")
    doc_ext: Optional[str] = Field(None, description="Filter documents by file extension (e.g., .pdf, .docx).")

    @field_validator(
        'document_ids', 'knowledge_space_id',
        mode='before', check_fields=False
    )
    @classmethod
    def uuid_from_bytes(cls, v):
        if isinstance(v, bytes):
            return uuid.UUID(bytes=v)
        if isinstance(v, list):
            return [uuid.UUID(bytes=i) if isinstance(i, bytes) else i for i in v]
        return v

    @root_validator(skip_on_failure=True)
    def check_exclusive_scope(cls, values):
        doc_ids_provided = bool(values.get('document_ids'))
        ks_id_provided = bool(values.get('knowledge_space_id'))

        if doc_ids_provided and ks_id_provided:
            raise ValueError("Provide either 'document_ids' or 'knowledge_space_id', but not both.")

        if not doc_ids_provided and not ks_id_provided:
            raise ValueError("Exactly one of 'document_ids' or 'knowledge_space_id' must be provided.")

        return values

class MultiGrepRequest(BaseModel):
    pattern: str = Field(..., description="The regular expression pattern to search for.")
    case_sensitive: bool = Field(False, description="Whether the pattern matching should be case-sensitive.")
    scope: GrepScope
    max_matches_per_doc: Optional[int] = Field(
        None,
        gt=0,
        description="Maximum number of matches to return per document. Overrides the server default."
    )
    context_lines_before: int = Field(
        0,
        ge=0,
        le=10,
        description="Number of lines to include before the matching line."
    )
    context_lines_after: int = Field(
        0,
        ge=0,
        le=10,
        description="Number of lines to include after the matching line."
    )

class DocumentGrepResult(BaseModel):
    document_id: uuid.UUID
    document_name: str
    matches: List[LineMatch]
    truncated: bool = Field(description="Indicates if the search for this document was stopped because max_matches_per_doc was reached.")

    @field_validator('document_id', mode='before', check_fields=False)
    @classmethod
    def uuid_from_bytes(cls, v):
        if isinstance(v, bytes):
            return uuid.UUID(bytes=v)
        return v

class GrepSummary(BaseModel):
    documents_searched: int = 0
    documents_with_matches: int = 0
    total_matches: int = 0
    results_truncated: bool = Field(description="Indicates if the results for any document were truncated.")

class MultiGrepResponse(BaseModel):
    summary: GrepSummary
    results: List[DocumentGrepResult]