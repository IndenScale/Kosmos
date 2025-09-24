import uuid
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from .user import UserRead

# Schema for adding a member to a knowledge space
class MemberAdd(BaseModel):
    user_id: uuid.UUID
    role: str = Field("viewer", pattern="^(owner|editor|viewer)$")

# Schema for reading member details
class MemberRead(BaseModel):
    user: UserRead
    role: str
    joined_at: datetime

    class Config:
        from_attributes = True
