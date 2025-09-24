import mimetypes
from typing import Optional


# 支持的文件类型白名单
SUPPORTED_MIME_TYPES = {
    # Office 2007+ 格式 (DOCX, PPTX, XLSX)
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # DOCX
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',  # PPTX
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # XLSX
    
    # Office 97-2003 格式 (DOC, PPT, XLS)
    'application/msword',  # DOC
    'application/vnd.ms-powerpoint',  # PPT
    'application/vnd.ms-excel',  # XLS
    
    # PDF
    'application/pdf',
}

# 文件扩展名到MIME类型的映射
EXTENSION_TO_MIME = {
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.doc': 'application/msword',
    '.ppt': 'application/vnd.ms-powerpoint',
    '.xls': 'application/vnd.ms-excel',
    '.pdf': 'application/pdf',
}

# 文件魔数签名
FILE_SIGNATURES = {
    # PDF 签名
    b'%PDF': 'application/pdf',
    
    # Office 2007+ 格式 (基于ZIP的格式)
    b'PK\x03\x04': 'application/zip',  # ZIP格式的开头，需要进一步检查
    
    # Office 97-2003 格式 (OLE格式)
    b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1': 'application/vnd.ms-office',
}


def detect_file_type_by_content(content: bytes) -> Optional[str]:
    """
    通过文件内容检测文件类型，使用模式匹配而非固定位置查找。
    处理嵌入文件可能带有Wrapper的情况。
    
    Args:
        content: 文件的二进制内容
        
    Returns:
        检测到的MIME类型，如果无法识别则返回None
    """
    if not content:
        return None
    
    # 搜索PDF签名（可能不在文件开头）
    pdf_pos = content.find(b'%PDF')
    if pdf_pos >= 0:  # 找到PDF签名
        if pdf_pos == 0:
            # 标准PDF文件
            return 'application/pdf'
        else:
            # 嵌入的PDF文档（有wrapper）
            return 'application/pdf'
    
    # 检查OLE格式（Office 97-2003）
    ole_signature = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'
    if ole_signature in content[:512]:  # 在前512字节中搜索
        return 'application/vnd.ms-office'
    
    # 检查ZIP格式（可能是Office 2007+格式）
    zip_signature = b'PK\x03\x04'
    if zip_signature in content[:512]:  # 在前512字节中搜索
        # 进一步检查是否为Office格式
        if is_office_zip_format(content):
            return detect_office_zip_type(content)
        return 'application/zip'
    
    return None


def is_office_zip_format(content: bytes) -> bool:
    """
    检查ZIP格式的文件是否为Office 2007+格式。
    Office文档包含特定的内部文件结构。
    
    Args:
        content: 文件的二进制内容
        
    Returns:
        如果是Office格式返回True，否则返回False
    """
    try:
        import zipfile
        import io
        
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            filenames = zf.namelist()
            
            # Office文档的特征文件
            office_indicators = [
                '[Content_Types].xml',
                '_rels/.rels',
                'word/',
                'ppt/',
                'xl/',
            ]
            
            return any(indicator in ''.join(filenames) for indicator in office_indicators)
    except:
        return False


def detect_office_zip_type(content: bytes) -> str:
    """
    检测Office ZIP格式的具体类型（DOCX, PPTX, XLSX）。
    
    Args:
        content: 文件的二进制内容
        
    Returns:
        具体的MIME类型
    """
    try:
        import zipfile
        import io
        
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            filenames = zf.namelist()
            filenames_str = ''.join(filenames)
            
            if 'word/' in filenames_str:
                return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            elif 'ppt/' in filenames_str:
                return 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
            elif 'xl/' in filenames_str:
                return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    except:
        pass
    
    # 默认返回通用的ZIP格式
    return 'application/zip'


def get_mime_type_from_filename(filename: str) -> Optional[str]:
    """
    根据文件名获取MIME类型。
    
    Args:
        filename: 文件名
        
    Returns:
        MIME类型，如果无法识别则返回None
    """
    if not filename:
        return None
    
    # 首先尝试从扩展名映射获取
    for ext, mime_type in EXTENSION_TO_MIME.items():
        if filename.lower().endswith(ext):
            return mime_type
    
    # 使用标准库的mimetypes模块
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type


def is_supported_file_type(filename: str, content: bytes, reported_mime_type: Optional[str] = None) -> bool:
    """
    检查文件是否为支持的类型。
    
    Args:
        filename: 文件名
        content: 文件内容
        reported_mime_type: 报告的MIME类型（可选）
        
    Returns:
        如果文件类型被支持返回True，否则返回False
    """
    # 1. 通过文件内容检测
    detected_mime = detect_file_type_by_content(content)
    if detected_mime and is_mime_type_supported(detected_mime):
        return True
    
    # 2. 通过文件名检测
    filename_mime = get_mime_type_from_filename(filename)
    if filename_mime and is_mime_type_supported(filename_mime):
        return True
    
    # 3. 检查报告的MIME类型
    if reported_mime_type and is_mime_type_supported(reported_mime_type):
        return True
    
    return False


def is_mime_type_supported(mime_type: str) -> bool:
    """
    检查MIME类型是否在支持的白名单中。
    
    Args:
        mime_type: MIME类型字符串
        
    Returns:
        如果支持返回True，否则返回False
    """
    if not mime_type:
        return False
    
    # 直接检查白名单
    if mime_type in SUPPORTED_MIME_TYPES:
        return True
    
    # 处理OLE格式的特殊情况
    if mime_type == 'application/vnd.ms-office':
        return True
    
    return False


def get_normalized_mime_type(filename: str, content: bytes, reported_mime_type: Optional[str] = None) -> Optional[str]:
    """
    获取标准化的MIME类型，优先使用内容检测。
    
    Args:
        filename: 文件名
        content: 文件内容
        reported_mime_type: 报告的MIME类型（可选）
        
    Returns:
        标准化的MIME类型，如果无法确定则返回None
    """
    # 1. 优先使用内容检测
    detected_mime = detect_file_type_by_content(content)
    if detected_mime and is_mime_type_supported(detected_mime):
        return detected_mime
    
    # 2. 使用文件名检测
    filename_mime = get_mime_type_from_filename(filename)
    if filename_mime and is_mime_type_supported(filename_mime):
        return filename_mime
    
    # 3. 使用报告的MIME类型
    if reported_mime_type and is_mime_type_supported(reported_mime_type):
        return reported_mime_type
    
    return None


def should_rename_embedded_pdf(filename: str, content: bytes, detected_mime: str) -> bool:
    """
    检查是否应该重命名嵌入的PDF文件。
    
    Args:
        filename: 原始文件名
        content: 文件内容
        detected_mime: 检测到的MIME类型
        
    Returns:
        如果应该重命名返回True，否则返回False
    """
    # 只有当文件名是.bin但内容是PDF时才需要重命名
    if not filename.lower().endswith('.bin'):
        return False
    
    if detected_mime != 'application/pdf':
        return False
    
    # 检查是否真的包含PDF内容
    pdf_pos = content.find(b'%PDF')
    return pdf_pos >= 0


def get_renamed_filename(original_filename: str, detected_mime: str) -> str:
    """
    根据检测到的MIME类型生成重命名后的文件名。
    
    Args:
        original_filename: 原始文件名
        detected_mime: 检测到的MIME类型
        
    Returns:
        重命名后的文件名
    """
    import os
    
    base_name, _ = os.path.splitext(original_filename)
    
    # 根据MIME类型确定新扩展名
    mime_to_extension = {
        'application/pdf': '.pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
        'application/msword': '.doc',
        'application/vnd.ms-powerpoint': '.ppt',
        'application/vnd.ms-excel': '.xls',
    }
    
    new_extension = mime_to_extension.get(detected_mime, '')
    if new_extension:
        return f"{base_name}{new_extension}"
    
    return original_filename


def should_trim_binary_wrapper(filename: str, content: bytes, detected_mime: str) -> bool:
    """
    检查是否应该裁剪二进制wrapper。
    
    Args:
        filename: 文件名
        content: 文件内容
        detected_mime: 检测到的MIME类型
        
    Returns:
        如果应该裁剪返回True，否则返回False
    """
    # 只有当检测到PDF但文件开头不是PDF签名时才需要裁剪
    if detected_mime != 'application/pdf':
        return False
    
    # 检查PDF签名位置
    pdf_pos = content.find(b'%PDF')
    return pdf_pos > 0  # PDF签名不在开头，说明有wrapper


def trim_binary_wrapper(content: bytes, detected_mime: str) -> bytes:
    """
    裁剪二进制wrapper，提取真实的文件内容。
    
    Args:
        content: 原始文件内容
        detected_mime: 检测到的MIME类型
        
    Returns:
        裁剪后的文件内容
    """
    if detected_mime == 'application/pdf':
        pdf_pos = content.find(b'%PDF')
        if pdf_pos > 0:
            return content[pdf_pos:]
    
    # 对于其他类型，暂时返回原内容
    return content


def process_embedded_file(filename: str, content: bytes, reported_mime_type: Optional[str] = None) -> tuple[str, bytes, str, bool, bool]:
    """
    处理嵌入文件，包括重命名和二进制裁剪。
    
    Args:
        filename: 原始文件名
        content: 文件内容
        reported_mime_type: 报告的MIME类型
        
    Returns:
        元组包含: (处理后的文件名, 处理后的内容, 标准化MIME类型, 是否重命名, 是否裁剪)
    """
    # 获取标准化MIME类型
    normalized_mime = get_normalized_mime_type(filename, content, reported_mime_type)
    
    if not normalized_mime:
        return filename, content, reported_mime_type or 'application/octet-stream', False, False
    
    # 检查是否需要重命名
    renamed = should_rename_embedded_pdf(filename, content, normalized_mime)
    new_filename = get_renamed_filename(filename, normalized_mime) if renamed else filename
    
    # 检查是否需要裁剪
    trimmed = should_trim_binary_wrapper(filename, content, normalized_mime)
    new_content = trim_binary_wrapper(content, normalized_mime) if trimmed else content
    
    return new_filename, new_content, normalized_mime, renamed, trimmed