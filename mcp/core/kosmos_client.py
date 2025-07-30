"""
Kosmos API客户端
负责与Kosmos后端API的通信
"""

import httpx
import asyncio
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class KosmosClient:
    """Kosmos API客户端"""
    
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.token = None
        self.headers = {"Content-Type": "application/json"}
        
    async def authenticate(self) -> bool:
        """认证并获取访问令牌"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/auth/login",
                    json={"username": self.username, "password": self.password}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self.token = data.get("access_token")
                    self.headers["Authorization"] = f"Bearer {self.token}"
                    logger.info("Kosmos认证成功")
                    return True
                else:
                    logger.error(f"Kosmos认证失败: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Kosmos认证异常: {str(e)}")
            return False
    
    async def request(self, method: str, endpoint: str, files: Optional[Dict] = None, data: Optional[Dict] = None, **kwargs) -> Dict[str, Any]:
        """统一的HTTP请求方法"""
        if not self.token:
            if not await self.authenticate():
                return {"error": "认证失败"}
        
        url = f"{self.base_url}{endpoint}"
        
        # 准备请求头
        request_headers = {"Authorization": f"Bearer {self.token}"}
        
        # 如果有文件上传，不设置Content-Type，让httpx自动处理
        if not files:
            request_headers["Content-Type"] = "application/json"
        
        try:
            async with httpx.AsyncClient() as client:
                # 准备请求参数
                request_kwargs = {
                    "method": method,
                    "url": url,
                    "headers": request_headers,
                    "timeout": 60.0,  # 文件上传可能需要更长时间
                    **kwargs
                }
                
                # 添加文件和数据
                if files:
                    request_kwargs["files"] = files
                if data:
                    request_kwargs["data"] = data
                
                response = await client.request(**request_kwargs)
                
                if response.status_code == 401:
                    # Token可能过期，重新认证
                    if await self.authenticate():
                        request_headers["Authorization"] = f"Bearer {self.token}"
                        request_kwargs["headers"] = request_headers
                        response = await client.request(**request_kwargs)
                
                if response.status_code >= 400:
                    return {
                        "error": f"HTTP {response.status_code}: {response.text}",
                        "status_code": response.status_code
                    }
                
                return response.json()
                
        except Exception as e:
            logger.error(f"请求失败 {method} {url}: {str(e)}")
            return {"error": f"请求异常: {str(e)}"}
    
    async def upload_file(self, kb_id: str, file_path: str, auto_parse: bool = True) -> Dict[str, Any]:
        """上传文件的便捷方法"""
        import os
        import aiofiles
        
        if not os.path.exists(file_path):
            return {"error": f"文件不存在: {file_path}"}
        
        try:
            async with aiofiles.open(file_path, 'rb') as f:
                file_content = await f.read()
            
            filename = os.path.basename(file_path)
            files = {
                'file': (filename, file_content, 'application/octet-stream')
            }
            data = {
                'auto_parse': str(auto_parse).lower()
            }
            
            return await self.request(
                "POST", 
                f"/api/v1/kbs/{kb_id}/documents/upload",
                files=files,
                data=data
            )
            
        except Exception as e:
            return {"error": f"文件上传异常: {str(e)}"}