import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..core.db import get_db
from ..schemas.user import UserCreate, UserRead
from ..services import user_service
from ..dependencies import get_current_user, require_super_admin
from ..models.user import User


router = APIRouter()

@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new user.
    """
    if user_service.get_user_by_username(db, username=user_in.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )
    if user_service.get_user_by_email(db, email=user_in.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    user = user_service.create_user(db=db, user_in=user_in)
    return user

@router.get("/me", response_model=UserRead)
def read_users_me(current_user: User = Depends(get_current_user)):
    """
    Get the details of the currently logged-in user.
    """
    return current_user

class UserRegisterRequest(BaseModel):
    username: str
    email: str
    display_name: str
    password: str
    role: str = "user"

class UserListResponse(BaseModel):
    users: List[UserRead]
    total: int

@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(
    user_data: UserRegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new user (CLI endpoint).
    """
    try:
        user = user_service.register_user(
            db=db,
            username=user_data.username,
            email=user_data.email,
            display_name=user_data.display_name,
            password=user_data.password,
            role=user_data.role
        )
        return user
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/", response_model=UserListResponse)
def list_users(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """
    List all users (admin only).
    """
    users, total = user_service.get_users_list(db, limit=limit, offset=offset)
    return UserListResponse(users=users, total=total)

@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
def delete_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Delete a user (admin only).
    """
    success = user_service.delete_user(db, str(user_id))
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return {"message": "User deleted successfully"}
