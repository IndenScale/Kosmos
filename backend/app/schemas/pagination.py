from typing import Generic, TypeVar, List
from pydantic import BaseModel, Field

DataType = TypeVar('DataType')

class PaginatedResponse(BaseModel, Generic[DataType]):
    items: List[DataType]
    total_count: int
    next_cursor: str | None = None

class PaginatedDocumentResponse(PaginatedResponse[DataType]):
    document_id_list: list[str] = Field(..., description="List of document IDs on the current page, as strings.")

class PaginatedJobResponse(PaginatedResponse[DataType]):
    job_id_list: list[str] = Field(..., description="List of job IDs on the current page, as strings.")
