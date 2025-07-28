#!/usr/bin/env python3
"""
测试文件上传大小限制
验证不同文件类型的大小限制是否正确配置
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.config import UploadConfig, FileCategory

def test_file_size_limits():
    """测试文件大小限制配置"""
    print("=== 文件大小限制测试 ===\n")
    
    # 测试不同文件类型的大小限制
    test_cases = [
        # PDF 文件
        ("document.pdf", "application/pdf", 500 * 1024 * 1024),  # 500MB
        ("large.pdf", "application/pdf", 600 * 1024 * 1024),    # 600MB (应该失败)
        
        # Office 文件
        ("presentation.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation", 500 * 1024 * 1024),
        ("large.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", 600 * 1024 * 1024),
        
        # 文本文件
        ("readme.txt", "text/plain", 50 * 1024 * 1024),   # 50MB
        ("large.txt", "text/plain", 60 * 1024 * 1024),    # 60MB (应该失败)
        
        # 图片文件
        ("image.png", "image/png", 20 * 1024 * 1024),     # 20MB
        ("large.jpg", "image/jpeg", 25 * 1024 * 1024),    # 25MB (应该失败)
        
        # 代码文件
        ("script.py", "text/x-python", 10 * 1024 * 1024), # 10MB
        ("large.js", "application/javascript", 15 * 1024 * 1024), # 15MB (应该失败)
    ]
    
    for filename, mime_type, file_size in test_cases:
        print(f"测试文件: {filename}")
        print(f"MIME类型: {mime_type}")
        print(f"文件大小: {file_size / (1024*1024):.1f}MB")
        
        # 检查文件是否支持
        if UploadConfig.is_supported_file(filename, mime_type):
            print("✓ 文件类型支持")
            
            # 获取最大允许大小
            max_size = UploadConfig.get_max_file_size(filename, mime_type)
            print(f"最大允许大小: {max_size / (1024*1024):.1f}MB")
            
            # 验证文件大小
            is_valid, error = UploadConfig.validate_file_size(filename, file_size, mime_type)
            if is_valid:
                print("✓ 文件大小验证通过")
            else:
                print(f"✗ 文件大小验证失败: {error}")
        else:
            print("✗ 文件类型不支持")
        
        print("-" * 50)

def test_supported_types():
    """测试支持的文件类型"""
    print("\n=== 支持的文件类型 ===\n")
    
    print("支持的文件扩展名:")
    extensions = UploadConfig.get_supported_extensions()
    for i, ext in enumerate(sorted(extensions), 1):
        print(f"{ext:>8}", end="")
        if i % 8 == 0:
            print()
    print("\n")
    
    print("支持的MIME类型:")
    mime_types = UploadConfig.get_supported_mime_types()
    for mime_type in sorted(mime_types):
        print(f"  {mime_type}")

def test_file_categories():
    """测试文件分类"""
    print("\n=== 文件分类测试 ===\n")
    
    test_files = [
        ("document.pdf", "application/pdf"),
        ("presentation.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        ("readme.txt", "text/plain"),
        ("image.png", "image/png"),
        ("script.py", "text/x-python"),
    ]
    
    for filename, mime_type in test_files:
        category = UploadConfig.get_file_category(filename, mime_type)
        max_size = UploadConfig.get_max_file_size(filename, mime_type)
        print(f"{filename:>15} -> {category.value:>8} (最大: {max_size/(1024*1024):>6.0f}MB)")

if __name__ == "__main__":
    test_file_size_limits()
    test_supported_types()
    test_file_categories()
    print("\n测试完成！")