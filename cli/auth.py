"""
此模块负责管理本地用户的认证凭证。

它处理 `~/.kosmos/credentials` 文件的创建、读取和写入，
并安全地存储Access Token和Refresh Token。
"""
import os
import configparser
from pathlib import Path
from datetime import datetime, timedelta, timezone

KOSMOS_DIR = Path.home() / ".kosmos"
CREDENTIALS_FILE = KOSMOS_DIR / "credentials"

def ensure_credentials_file_exists():
    """
    确保 `~/.kosmos/credentials` 文件和目录存在，并设置安全的文件权限。
    """
    try:
        KOSMOS_DIR.mkdir(exist_ok=True)
        # 设置目录权限为 700 (drwx------)
        KOSMOS_DIR.chmod(0o700)
        
        if not CREDENTIALS_FILE.exists():
            CREDENTIALS_FILE.touch()
        
        # 设置文件权限为 600 (-rw-------)
        CREDENTIALS_FILE.chmod(0o600)
    except OSError as e:
        print(f"错误: 无法创建或设置凭证文件的权限: {e}")
        raise

def save_tokens(access_token: str, refresh_token: str, expires_in_minutes: int = 30):
    """
    将Access Token和Refresh Token保存到凭证文件中。
    """
    ensure_credentials_file_exists()
    config = configparser.ConfigParser()
    
    # 计算过期时间并存储为ISO 8601格式
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes)
    
    config['default'] = {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'expires_at': expires_at.isoformat()
    }
    
    with open(CREDENTIALS_FILE, 'w') as configfile:
        config.write(configfile)
    print("凭证已成功保存。")

def load_tokens() -> dict | None:
    """
    从凭证文件中加载Tokens。
    如果文件不存在或为空，则返回None。
    """
    if not CREDENTIALS_FILE.exists():
        return None
        
    config = configparser.ConfigParser()
    config.read(CREDENTIALS_FILE)
    
    if 'default' in config and 'access_token' in config['default']:
        return dict(config['default'])
    
    return None

def is_token_expired(token_data: dict) -> bool:
    """
    根据存储的过期时间检查Access Token是否已过期。
    """
    expires_at_str = token_data.get('expires_at')
    if not expires_at_str:
        # 如果没有过期时间信息，则认为已过期
        return True
    
    try:
        expires_at = datetime.fromisoformat(expires_at_str)
        # 增加一个30秒的缓冲，以应对网络延迟
        return datetime.now(timezone.utc) > (expires_at - timedelta(seconds=30))
    except ValueError:
        # 如果时间格式错误，则认为已过期
        return True
