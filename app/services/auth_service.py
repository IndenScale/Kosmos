from tkinter.constants import FALSE
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from datetime import datetime, timedelta, timezone
import secrets
import uuid

from app.models.user import User
from app.schemas.user import UserLogin, PasswordResetRequest, PasswordReset, TokenRefresh
from app.dependencies.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS
)

class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def authenticate_user(self, username: str, password: str) -> User:
        """验证用户登录"""
        user = self.db.query(User).filter(User.username == username).first()
        if not user or not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    def login(self, login_data: UserLogin) -> dict:
        """用户登录"""
        user = self.authenticate_user(login_data.username, login_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 创建访问令牌和刷新令牌
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.id, "role": user.role},
            expires_delta=access_token_expires
        )

        refresh_token_expires = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        refresh_token = create_refresh_token(
            data={"sub": user.id},
            expires_delta=refresh_token_expires
        )

        # 保存刷新令牌到数据库
        user.refresh_token = refresh_token
        user.refresh_token_expires = datetime.now(timezone.utc) + refresh_token_expires
        self.db.commit()

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "created_at": user.created_at,
                "is_active": user.is_active
            }
        }

    def refresh_token(self, token_data: TokenRefresh) -> dict:
        """刷新访问令牌"""
        try:
            # 验证刷新令牌
            payload = verify_refresh_token(token_data.refresh_token)
            user_id = payload.get("sub")

            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="无效的刷新令牌"
                )

            # 从数据库验证刷新令牌
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user or not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="用户不存在或已被禁用"
                )

            if (user.refresh_token != token_data.refresh_token or
                user.refresh_token_expires < datetime.now(timezone.utc)):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="刷新令牌已过期或无效"
                )

            # 创建新的访问令牌
            access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(
                data={"sub": user.id, "role": user.role},
                expires_delta=access_token_expires
            )

            # 可选：创建新的刷新令牌
            refresh_token_expires = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
            new_refresh_token = create_refresh_token(
                data={"sub": user.id},
                expires_delta=refresh_token_expires
            )

            # 更新数据库中的刷新令牌
            user.refresh_token = new_refresh_token
            user.refresh_token_expires = datetime.now(timezone.utc) + refresh_token_expires
            self.db.commit()

            return {
                "access_token": access_token,
                "refresh_token": new_refresh_token,
                "token_type": "bearer"
            }

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="刷新令牌验证失败"
            )

    def logout(self, user_id: str) -> bool:
        """用户登出，清除刷新令牌"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if user:
            user.refresh_token = None
            user.refresh_token_expires = None
            self.db.commit()
            return True
        return False

    def request_password_reset(self, reset_data: PasswordResetRequest) -> bool:
        """请求密码重置"""
        # 尚未实现
        return FALSE
        user = self.db.query(User).filter(User.email == reset_data.email).first()
        if not user:
            # 为了安全，即使用户不存在也返回成功
            return True

        # 生成重置令牌
        reset_token = secrets.token_urlsafe(32)
        reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)  # 1小时有效期

        user.reset_token = reset_token
        user.reset_token_expires = reset_expires
        self.db.commit()

        # TODO: 在这里发送重置邮件
        # send_password_reset_email(user.email, reset_token)

        return True

    def reset_password(self, reset_data: PasswordReset) -> bool:
        """重置密码"""
        user = self.db.query(User).filter(
            User.reset_token == reset_data.token
        ).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无效的重置令牌"
            )

        if user.reset_token_expires < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="重置令牌已过期"
            )

        # 更新密码
        user.password_hash = get_password_hash(reset_data.new_password)
        user.reset_token = None
        user.reset_token_expires = None

        # 清除所有刷新令牌，强制重新登录
        user.refresh_token = None
        user.refresh_token_expires = None

        self.db.commit()
        return True