"""
文件处理工具模块
提供文件哈希计算、MIME类型检测等通用文件处理功能
"""

import hashlib
import mimetypes
import os
from typing import Tuple, Optional


def calculate_file_hash(content: bytes, algorithm: str = "sha256") -> str:
    """
    计算文件内容的哈希值
    
    Args:
        content: 文件内容字节
        algorithm: 哈希算法，默认为sha256
        
    Returns:
        十六进制格式的哈希字符串
    """
    if algorithm.lower() == "sha256":
        return hashlib.sha256(content).hexdigest()
    elif algorithm.lower() == "md5":
        return hashlib.md5(content).hexdigest()
    else:
        raise ValueError(f"不支持的哈希算法: {algorithm}")


def detect_mime_type(filename: str, fallback: str = "application/octet-stream") -> str:
    """
    检测文件的MIME类型
    
    Args:
        filename: 文件名
        fallback: 如果无法检测时的默认MIME类型
        
    Returns:
        检测到的MIME类型或fallback值
    """
    detected_mime_type, _ = mimetypes.guess_type(filename)
    return detected_mime_type or fallback


def get_file_extension(filename: str) -> str:
    """
    获取文件扩展名
    
    Args:
        filename: 文件名
        
    Returns:
        文件扩展名（包含点号），如果没有扩展名则返回空字符串
    """
    _, extension = os.path.splitext(filename)
    return extension


def generate_object_name(file_hash: str, filename: str) -> str:
    """
    根据文件哈希和文件名生成对象存储中的对象名称
    
    Args:
        file_hash: 文件哈希值
        filename: 原始文件名
        
    Returns:
        对象存储中的对象名称
    """
    extension = get_file_extension(filename)
    return f"{file_hash}{extension}"


def unwrap_ole_and_correct_info(
    content: bytes, filename: str, mime_type: str
) -> Tuple[bytes, str, str]:
    """
    检查文件内容是否为 OLE 包装的 PDF，如果是，则剥离包装并修正文件信息。

    Args:
        content: 原始文件内容的字节流。
        filename: 原始文件名。
        mime_type: 原始MIME类型。

    Returns:
        一个元组，包含 (处理后的内容, 修正后的文件名, 修正后的MIME类型)。
        如果不是 OLE 包装的 PDF，则返回原始输入。
    """
    # PDF 的魔法数是 %PDF- (0x25 0x50 0x44 0x46 0x2D)
    PDF_MAGIC_NUMBER = b'%PDF-'
    
    # 仅当文件被识别为通用二进制流或.bin文件时，才进行检查
    is_candidate = mime_type == "application/octet-stream" or filename.lower().endswith('.bin')
    
    if is_candidate:
        offset = content.find(PDF_MAGIC_NUMBER)
        
        # 如果找到了 PDF 魔法数，并且它不在文件的开头
        if offset > 0:
            print(f"  - Found embedded PDF in '{filename}' at offset {offset}. Stripping OLE wrapper.")
            
            # 剥离 OLE 头部
            unwrapped_content = content[offset:]
            
            # 修正文件名和 MIME 类型
            base_name, _ = os.path.splitext(filename)
            new_filename = f"{base_name}.pdf"
            new_mime_type = "application/pdf"
            
            print(f"  - Corrected filename to '{new_filename}' and MIME type to '{new_mime_type}'.")
            return unwrapped_content, new_filename, new_mime_type
            
    return content, filename, mime_type
