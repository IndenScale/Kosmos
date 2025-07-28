from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.user import (
    UserRegister, UserResponse, Token, UserLogin,
    PasswordResetRequest, PasswordReset, TokenRefresh, TokenResponse
)
from app.services.user_service import UserService
from app.services.auth_service import AuthService
from app.dependencies.auth import get_current_active_user
from app.models.user import User

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user_data: UserRegister, db: Session = Depends(get_db)):
    """用户注册"""
    user_service = UserService(db)
    user = user_service.create_user(user_data)
    return user

@router.post("/login", response_model=Token)
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    """用户登录"""
    auth_service = AuthService(db)
    return auth_service.login(login_data)

@router.post("/token", response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """OAuth2兼容的用户登录获取访问令牌"""
    auth_service = AuthService(db)
    login_data = UserLogin(username=form_data.username, password=form_data.password)
    return auth_service.login(login_data)

@router.post("/refresh", response_model=TokenResponse)
def refresh_access_token(token_data: TokenRefresh, db: Session = Depends(get_db)):
    """刷新访问令牌"""
    auth_service = AuthService(db)
    return auth_service.refresh_token(token_data)

@router.post("/logout")
def logout(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """用户登出"""
    auth_service = AuthService(db)
    success = auth_service.logout(current_user.id)
    if success:
        return {"message": "登出成功"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="登出失败"
        )

@router.post("/password-reset-request")
def request_password_reset(reset_data: PasswordResetRequest, db: Session = Depends(get_db)):
    """请求密码重置"""
    auth_service = AuthService(db)
    success = auth_service.request_password_reset(reset_data)
    if success:
        return {"message": "如果邮箱存在，重置链接已发送"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="密码重置功能尚未实现"
        )

@router.post("/password-reset")
def reset_password(reset_data: PasswordReset, db: Session = Depends(get_db)):
    """重置密码"""
    auth_service = AuthService(db)
    success = auth_service.reset_password(reset_data)
    if success:
        return {"message": "密码重置成功"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="密码重置失败"
        )

@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """获取当前用户信息"""
    return current_user
