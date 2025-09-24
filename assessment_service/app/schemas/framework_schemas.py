"""
Pydantic schemas for Assessment Frameworks and Control Item Definitions.

These schemas are used for API request and response validation, and for
passing structured data between the API layer and the service layer.
"""
from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID

# --- Control Item Definition Schemas ---

class ControlItemDefinitionBase(BaseModel):
    display_id: str
    content: str
    parent_id: Optional[UUID] = None
    assessment_guidance: Optional[dict] = None
    details: Optional[dict] = None

class ControlItemDefinitionCreate(ControlItemDefinitionBase):
    pass

class ControlItemDefinitionResponse(ControlItemDefinitionBase):
    id: UUID
    
    class Config:
        from_attributes = True

# --- Framework Schemas ---

class FrameworkBase(BaseModel):
    name: str
    version: str
    description: Optional[str] = None
    source: Optional[str] = None

class FrameworkCreate(FrameworkBase):
    pass

class FrameworkResponse(FrameworkBase):
    id: UUID
    control_item_definitions: List[ControlItemDefinitionResponse] = []

    class Config:
        from_attributes = True
