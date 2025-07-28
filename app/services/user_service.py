from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from typing import Optional, List

from app.models.user import User
from app.schemas.user import UserRegister, UserUpdate, PasswordChange
from app.dependencies.auth import get_password_hash, verify_password

class UserService:
    def __init__(self, db: Session):
        self.db = db

    def create_user(self, user_data: UserRegister) -> User:
        """创建新用户"""
        # 检查用户名是否已存在
        if self.db.query(User).filter(User.username == user_data.username).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已被注册"
            )

        # 检查邮箱是否已存在
        if self.db.query(User).filter(User.email == user_data.email).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已被注册"
            )

        # 创建新用户
        hashed_password = get_password_hash(user_data.password)
        db_user = User(
            username=user_data.username,
            email=user_data.email,
            password_hash=hashed_password
        )

        try:
            self.db.add(db_user)
            self.db.commit()
            self.db.refresh(db_user)
            return db_user
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户注册失败"
            )

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """根据ID获取用户"""
        return self.db.query(User).filter(User.id == user_id).first()

    def get_user_by_username(self, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        return self.db.query(User).filter(User.username == username).first()

    def get_user_by_email(self, email: str) -> Optional[User]:
        """根据邮箱获取用户"""
        return self.db.query(User).filter(User.email == email).first()

    def get_users(self, skip: int = 0, limit: int = 100, active_only: bool = True) -> List[User]:
        """获取用户列表"""
        query = self.db.query(User)
        if active_only:
            query = query.filter(User.is_active == True)
        return query.offset(skip).limit(limit).all()

    def update_user(self, user_id: str, user_data: UserUpdate) -> User:
        """更新用户信息"""
        user = self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )

        # 检查用户名是否已被其他用户使用
        if user_data.username and user_data.username != user.username:
            existing_user = self.get_user_by_username(user_data.username)
            if existing_user and existing_user.id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="用户名已被使用"
                )

        # 检查邮箱是否已被其他用户使用
        if user_data.email and user_data.email != user.email:
            existing_user = self.get_user_by_email(user_data.email)
            if existing_user and existing_user.id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="邮箱已被使用"
                )

        # 更新用户信息
        update_data = user_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)

        try:
            self.db.commit()
            self.db.refresh(user)
            return user
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户信息更新失败"
            )

    def change_password(self, user_id: str, password_data: PasswordChange) -> bool:
        """修改用户密码"""
        user = self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )

        # 验证当前密码
        if not verify_password(password_data.current_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当前密码错误"
            )

        # 更新密码
        user.password_hash = get_password_hash(password_data.new_password)
        
        # 清除刷新令牌，强制重新登录
        user.refresh_token = None
        user.refresh_token_expires = None

        try:
            self.db.commit()
            return True
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="密码修改失败"
            )

    def deactivate_user(self, user_id: str) -> bool:
        """停用用户"""
        user = self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )

        user.is_active = False
        # 清除刷新令牌
        user.refresh_token = None
        user.refresh_token_expires = None

        try:
            self.db.commit()
            return True
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户停用失败"
            )

    def activate_user(self, user_id: str) -> bool:
        """激活用户"""
        user = self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )

        user.is_active = True

        try:
            self.db.commit()
            return True
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户激活失败"
            )

    def delete_user(self, user_id: str) -> bool:
        """删除用户（软删除，实际上是停用）"""
        return self.deactivate_user(user_id)