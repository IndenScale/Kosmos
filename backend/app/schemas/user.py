import uuid
from pydantic import BaseModel, EmailStr, field_validator

# Shared properties
class UserBase(BaseModel):
    username: str
    email: EmailStr
    display_name: str

# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str

# Properties to receive via API on update
class UserUpdate(UserBase):
    password: str | None = None

# Properties shared by models stored in DB
class UserInDBBase(UserBase):
    id: uuid.UUID
    role: str

    class Config:
        from_attributes = True

# Properties to return to client
class UserRead(UserInDBBase):
    pass

# Properties stored in DB
class UserInDB(UserInDBBase):
    hashed_password: str
