from datetime import datetime, timedelta, timezone
import secrets
import uuid
from jose import jwt, JWTError
from passlib.context import CryptContext
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.user import User
from ..models.refresh_token import RefreshToken

# --- Password Hashing ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码与哈希密码是否匹配"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """生成密码的哈希值"""
    return pwd_context.hash(password)

# --- JWT Access Token Creation ---
def create_access_token(user: User) -> str:
    """
    根据用户角色生成JWT Access Token。
    """
    to_encode = {"sub": str(user.id)}

    if user.role == "super_admin":
        expire_minutes = settings.SUPER_ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES
    else:
        expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES

    expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    to_encode.update({"exp": expire, "type": "access"})

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

# --- Refresh Token Management ---
def create_refresh_token(db: Session, user_id: uuid.UUID) -> str:
    """
    为指定用户创建一个新的Refresh Token，并将其存入数据库。
    """
    expire_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    expires_at = datetime.now(timezone.utc) + expire_delta
    
    # 创建一个安全的、随机的令牌字符串
    token_str = secrets.token_urlsafe(32)
    
    db_refresh_token = RefreshToken(
        token=token_str,
        user_id=user_id,
        expires_at=expires_at
    )
    db.add(db_refresh_token)
    db.commit()
    db.refresh(db_refresh_token)
    
    return token_str

def get_user_from_refresh_token(db: Session, token: str) -> User:
    """
    验证一个Refresh Token并返回其关联的用户。
    如果Token无效、过期或已被撤销，则抛出异常。
    """
    db_token = db.query(RefreshToken).filter(RefreshToken.token == token).first()
    
    if not db_token:
        raise JWTError("Refresh token not found")
    if db_token.is_revoked:
        raise JWTError("Refresh token has been revoked")
    if db_token.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise JWTError("Refresh token has expired")
        
    user = db.query(User).filter(User.id == db_token.user_id).first()
    if not user:
        raise JWTError("User associated with refresh token not found")
        
    return user

# --- API Key Encryption ---
try:
    fernet = Fernet(settings.CREDENTIAL_ENCRYPTION_KEY.encode())
except Exception as e:
    raise ValueError(f"Invalid CREDENTIAL_ENCRYPTION_KEY: {e}. Please generate a valid key.")

def encrypt_api_key(api_key: str) -> str:
    """Encrypts an API key using Fernet symmetric encryption."""
    if not api_key:
        return ""
    return fernet.encrypt(api_key.encode()).decode()

def decrypt_api_key(encrypted_api_key: str) -> str:
    """Decrypts an API key using Fernet symmetric encryption."""
    if not encrypted_api_key:
        return ""
    return fernet.decrypt(encrypted_api_key.encode()).decode()
