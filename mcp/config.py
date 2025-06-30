"""
配置管理模块
"""
import os
from typing import Optional
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class KosmosConfig:
    """Kosmos配置类"""
    
    def __init__(self):
        self.base_url = os.getenv('KOSMOS_BASE_URL', 'http://localhost:8000')
        self.username = os.getenv('KOSMOS_USERNAME')
        self.password = os.getenv('KOSMOS_PASSWORD')  
    
    def validate(self) -> bool:
        """验证配置是否完整"""
        if not self.base_url:
            return False
        # 至少需要有用户名密码或API密钥中的一种认证方式
        if not (self.username and self.password):
            print("警告: 未配置认证信息")
            return False
        return True
    
    def get_auth_info(self) -> dict:
        """获取认证信息"""
        return {
            'base_url': self.base_url,
            'username': self.username,
            'password': self.password
        }