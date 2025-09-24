
import uuid
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

# --- Schemas for Reading Document Content ---

class AssetInContent(BaseModel):
    asset_id: uuid.UUID
    asset_type: str
    description: Optional[str] = None

    @field_validator('asset_id', mode='before', check_fields=False)
    @classmethod
    def uuid_from_bytes(cls, v):
        if isinstance(v, bytes):
            return uuid.UUID(bytes=v)
        return v

class LineWithMeta(BaseModel):
    line: int
    page: Optional[int] = None
    content: str

# This is the DocumentReadResponse the system was looking for.
class DocumentReadResponse(BaseModel):
    char_count: int
    start_line: int
    end_line: int
    total_lines: int
    assets: List[AssetInContent]
    lines: List[LineWithMeta]
    relevant_page_numbers: List[int]

    class Config:
        from_attributes = True

# --- Schemas for Grep Functionality ---

class GrepRequest(BaseModel):
    pattern: str = Field(description="The regular expression pattern to search for.")
    case_sensitive: bool = Field(default=False, description="Perform case-sensitive matching.")
    context_lines_before: int = Field(default=0, ge=0, le=10, description="Number of lines to show before the matching line.")
    context_lines_after: int = Field(default=0, ge=0, le=10, description="Number of lines to show after the matching line.")
    max_matches: Optional[int] = Field(default=None, gt=0, description="Stop reading after this many matches.")


# --- Schemas for PDF Page Requests ---

class PageImageRequest(BaseModel):
    pages: List[str] = Field(
        ...,
        description="A list of page specifications. Accepts single pages ('5'), ranges ('8-12'), or a mix.",
        examples=[["1", "5", "8-12", "15"]]
    )
