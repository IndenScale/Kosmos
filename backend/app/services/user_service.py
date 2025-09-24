from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..models.user import User
from ..schemas.user import UserCreate
from ..core.security import get_password_hash, verify_password

def get_user_by_email(db: Session, email: str) -> User | None:
    """通过邮箱地址查询用户"""
    return db.query(User).filter(User.email == email).first()

def get_user_by_username(db: Session, username: str) -> User | None:
    """通过用户名查询用户"""
    return db.query(User).filter(User.username == username).first()

def create_user(db: Session, user_in: UserCreate) -> User:
    """
    创建新用户。
    如果数据库中没有用户，则将第一个用户设为 super_admin。
    """
    # 检查是否是第一个用户
    user_count = db.query(User).count()
    if user_count == 0:
        role = "super_admin"
    else:
        role = "user"

    hashed_password = get_password_hash(user_in.password)
    db_user = User(
        username=user_in.username,
        email=user_in.email,
        display_name=user_in.display_name,
        hashed_password=hashed_password,
        role=role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def authenticate_user(db: Session, identifier: str, password: str) -> User | None:
    """
    验证用户凭据。
    identifier 可以是 username 或 email。
    如果凭据有效，则返回用户对象；否则返回 None。
    """
    user = None
    if "@" in identifier:
        user = get_user_by_email(db, email=identifier)
    else:
        user = get_user_by_username(db, username=identifier)
    
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

def get_user_by_id(db: Session, user_id: str) -> User | None:
    """通过用户ID查询用户"""
    return db.query(User).filter(User.id == user_id).first()

def get_users_list(db: Session, limit: int = 20, offset: int = 0) -> tuple[List[User], int]:
    """获取用户列表，返回用户列表和总数"""
    total = db.query(func.count(User.id)).scalar()
    users = db.query(User).offset(offset).limit(limit).all()
    return users, total

def delete_user(db: Session, user_id: str) -> bool:
    """删除用户，返回是否成功"""
    user = get_user_by_id(db, user_id)
    if not user:
        return False
    
    db.delete(user)
    db.commit()
    return True

def register_user(db: Session, username: str, email: str, display_name: str, password: str, role: str = "user") -> User:
    """注册新用户（CLI专用）"""
    # 检查用户名是否已存在
    if get_user_by_username(db, username):
        raise ValueError("Username already exists")
    
    # 检查邮箱是否已存在
    if get_user_by_email(db, email):
        raise ValueError("Email already exists")
    
    # 创建用户
    user_in = UserCreate(
        username=username,
        email=email,
        display_name=display_name,
        password=password
    )
    
    hashed_password = get_password_hash(password)
    db_user = User(
        username=username,
        email=email,
        display_name=display_name,
        hashed_password=hashed_password,
        role=role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user
