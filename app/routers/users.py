from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List

from app.db.database import get_db
from app.schemas.user import UserResponse, UserUpdate, PasswordChange
from app.services.user_service import UserService
from app.dependencies.auth import get_current_active_user, require_admin, require_system_admin
from app.models.user import User

router = APIRouter(prefix="/api/v1/users", tags=["users"])

@router.get("/me", response_model=UserResponse)
def get_my_profile(current_user: User = Depends(get_current_active_user)):
    """获取当前用户资料"""
    return current_user

@router.put("/me", response_model=UserResponse)
def update_my_profile(
    user_data: UserUpdate, 
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """更新当前用户资料"""
    user_service = UserService(db)
    return user_service.update_user(current_user.id, user_data)

@router.post("/me/change-password")
def change_my_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """修改当前用户密码"""
    user_service = UserService(db)
    success = user_service.change_password(current_user.id, password_data)
    if success:
        return {"message": "密码修改成功"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="密码修改失败"
        )

@router.delete("/me")
def deactivate_my_account(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """停用当前用户账户"""
    user_service = UserService(db)
    success = user_service.deactivate_user(current_user.id)
    if success:
        return {"message": "账户已停用"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="账户停用失败"
        )

# 管理员功能
@router.get("/", response_model=List[UserResponse])
def get_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    active_only: bool = Query(True),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """获取用户列表（管理员权限）"""
    user_service = UserService(db)
    return user_service.get_users(skip=skip, limit=limit, active_only=active_only)

@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """获取指定用户信息（管理员权限）"""
    user_service = UserService(db)
    user = user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    return user

@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    user_data: UserUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """更新指定用户信息（管理员权限）"""
    user_service = UserService(db)
    return user_service.update_user(user_id, user_data)

@router.post("/{user_id}/deactivate")
def deactivate_user(
    user_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """停用指定用户（管理员权限）"""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能停用自己的账户"
        )
    
    user_service = UserService(db)
    success = user_service.deactivate_user(user_id)
    if success:
        return {"message": "用户已停用"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户停用失败"
        )

@router.post("/{user_id}/activate")
def activate_user(
    user_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """激活指定用户（管理员权限）"""
    user_service = UserService(db)
    success = user_service.activate_user(user_id)
    if success:
        return {"message": "用户已激活"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户激活失败"
        )

# 系统管理员功能
@router.delete("/{user_id}")
def delete_user(
    user_id: str,
    current_user: User = Depends(require_system_admin),
    db: Session = Depends(get_db)
):
    """删除指定用户（系统管理员权限）"""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己的账户"
        )
    
    user_service = UserService(db)
    success = user_service.delete_user(user_id)
    if success:
        return {"message": "用户已删除"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户删除失败"
        )