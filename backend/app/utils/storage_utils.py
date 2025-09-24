"""
存储工具模块
提供MinIO对象存储相关的工具函数
"""

from typing import Tuple
from minio import Minio


def parse_storage_path(storage_path: str) -> Tuple[str, str]:
    """
    解析存储路径，提取bucket名称和对象名称
    
    Args:
        storage_path: 存储路径，格式如"/bucket_name/object_name"
        
    Returns:
        包含(bucket_name, object_name)的元组
        
    Raises:
        ValueError: 如果存储路径格式无效
    """
    if not storage_path.startswith('/'):
        raise ValueError("存储路径必须以'/'开头")
    
    parts = storage_path.split('/', 2)
    if len(parts) < 3:
        raise ValueError("存储路径格式无效，应为'/bucket_name/object_name'")
    
    bucket_name = parts[1]
    object_name = parts[2]
    
    return bucket_name, object_name


async def upload_file_to_minio(
    minio: Minio,
    bucket_name: str,
    object_name: str,
    file_data,
    file_size: int,
    content_type: str
) -> None:
    """
    上传文件到MinIO
    
    Args:
        minio: MinIO客户端实例
        bucket_name: 存储桶名称
        object_name: 对象名称
        file_data: 文件数据
        file_size: 文件大小
        content_type: 文件内容类型
    """
    minio.put_object(
        bucket_name=bucket_name,
        object_name=object_name,
        data=file_data,
        length=file_size,
        content_type=content_type
    )


def download_file_from_minio(minio: Minio, bucket_name: str, object_name: str):
    """
    从MinIO下载文件
    
    Args:
        minio: MinIO客户端实例
        bucket_name: 存储桶名称
        object_name: 对象名称
        
    Returns:
        MinIO响应对象
    """
    return minio.get_object(
        bucket_name=bucket_name,
        object_name=object_name
    )


def generate_storage_path(bucket_name: str, object_name: str) -> str:
    """
    生成存储路径
    
    Args:
        bucket_name: 存储桶名称
        object_name: 对象名称
        
    Returns:
        存储路径字符串
    """
    return f"/{bucket_name}/{object_name}"