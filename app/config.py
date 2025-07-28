import logging
import os
from pathlib import Path
from pydantic import BaseModel
from typing import Optional, Dict, Set, Tuple
from enum import Enum

# ============================================================================
# 文件上传配置
# ============================================================================

class FileCategory(Enum):
    """文件类别枚举"""
    PDF = "pdf"
    OFFICE = "office"
    TEXT = "text"
    IMAGE = "image"
    CODE = "code"

class UploadConfig:
    """文件上传配置类"""
    
    # 文件大小限制 (单位: MB)
    FILE_SIZE_LIMITS = {
        FileCategory.PDF: 500,      # PDF文件限制500MB
        FileCategory.OFFICE: 500,   # Office文件限制500MB
        FileCategory.TEXT: 50,      # 文本文件限制50MB
        FileCategory.IMAGE: 20,     # 图片文件限制20MB
        FileCategory.CODE: 10,      # 代码文件限制10MB
    }
    
    # MIME类型到文件类别的映射
    MIME_TYPE_MAPPING = {
        # PDF文件
        "application/pdf": FileCategory.PDF,
        
        # Office文件
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": FileCategory.OFFICE,  # .docx
        "application/msword": FileCategory.OFFICE,  # .doc
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": FileCategory.OFFICE,  # .pptx
        "application/vnd.ms-powerpoint": FileCategory.OFFICE,  # .ppt
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": FileCategory.OFFICE,  # .xlsx
        "application/vnd.ms-excel": FileCategory.OFFICE,  # .xls
        
        # 文本文件
        "text/plain": FileCategory.TEXT,
        "text/markdown": FileCategory.TEXT,
        "text/csv": FileCategory.TEXT,
        "application/json": FileCategory.TEXT,
        "application/xml": FileCategory.TEXT,
        "text/xml": FileCategory.TEXT,
        "application/yaml": FileCategory.TEXT,
        "text/yaml": FileCategory.TEXT,
        
        # 图片文件
        "image/png": FileCategory.IMAGE,
        "image/jpeg": FileCategory.IMAGE,
        "image/jpg": FileCategory.IMAGE,
        "image/gif": FileCategory.IMAGE,
        "image/bmp": FileCategory.IMAGE,
        "image/webp": FileCategory.IMAGE,
        "image/svg+xml": FileCategory.IMAGE,
        
        # 代码文件 (通过扩展名识别)
        "text/x-python": FileCategory.CODE,
        "application/javascript": FileCategory.CODE,
        "text/javascript": FileCategory.CODE,
        "application/typescript": FileCategory.CODE,
        "text/x-java-source": FileCategory.CODE,
        "text/x-c": FileCategory.CODE,
        "text/x-c++": FileCategory.CODE,
        "text/html": FileCategory.CODE,
        "text/css": FileCategory.CODE,
    }
    
    # 文件扩展名到文件类别的映射
    EXTENSION_MAPPING = {
        # PDF文件
        '.pdf': FileCategory.PDF,
        
        # Office文件
        '.docx': FileCategory.OFFICE,
        '.doc': FileCategory.OFFICE,
        '.pptx': FileCategory.OFFICE,
        '.ppt': FileCategory.OFFICE,
        '.xlsx': FileCategory.OFFICE,
        '.xls': FileCategory.OFFICE,
        
        # 文本文件
        '.txt': FileCategory.TEXT,
        '.md': FileCategory.TEXT,
        '.markdown': FileCategory.TEXT,
        '.csv': FileCategory.TEXT,
        '.json': FileCategory.TEXT,
        '.xml': FileCategory.TEXT,
        '.yaml': FileCategory.TEXT,
        '.yml': FileCategory.TEXT,
        '.log': FileCategory.TEXT,
        '.cfg': FileCategory.TEXT,
        '.conf': FileCategory.TEXT,
        '.ini': FileCategory.TEXT,
        
        # 图片文件
        '.png': FileCategory.IMAGE,
        '.jpg': FileCategory.IMAGE,
        '.jpeg': FileCategory.IMAGE,
        '.gif': FileCategory.IMAGE,
        '.bmp': FileCategory.IMAGE,
        '.webp': FileCategory.IMAGE,
        '.svg': FileCategory.IMAGE,
        
        # 代码文件
        '.py': FileCategory.CODE,
        '.js': FileCategory.CODE,
        '.ts': FileCategory.CODE,
        '.tsx': FileCategory.CODE,
        '.jsx': FileCategory.CODE,
        '.java': FileCategory.CODE,
        '.c': FileCategory.CODE,
        '.cpp': FileCategory.CODE,
        '.cc': FileCategory.CODE,
        '.cxx': FileCategory.CODE,
        '.h': FileCategory.CODE,
        '.hpp': FileCategory.CODE,
        '.cs': FileCategory.CODE,
        '.php': FileCategory.CODE,
        '.rb': FileCategory.CODE,
        '.go': FileCategory.CODE,
        '.rs': FileCategory.CODE,
        '.swift': FileCategory.CODE,
        '.kt': FileCategory.CODE,
        '.scala': FileCategory.CODE,
        '.html': FileCategory.CODE,
        '.htm': FileCategory.CODE,
        '.css': FileCategory.CODE,
        '.scss': FileCategory.CODE,
        '.sass': FileCategory.CODE,
        '.less': FileCategory.CODE,
        '.sql': FileCategory.CODE,
        '.sh': FileCategory.CODE,
        '.bash': FileCategory.CODE,
        '.zsh': FileCategory.CODE,
        '.fish': FileCategory.CODE,
        '.ps1': FileCategory.CODE,
        '.bat': FileCategory.CODE,
        '.cmd': FileCategory.CODE,
        '.dockerfile': FileCategory.CODE,
        '.makefile': FileCategory.CODE,
        '.r': FileCategory.CODE,
        '.m': FileCategory.CODE,
        '.pl': FileCategory.CODE,
        '.lua': FileCategory.CODE,
        '.vim': FileCategory.CODE,
        '.toml': FileCategory.CODE,
    }
    
    @classmethod
    def get_file_category(cls, filename: str, mime_type: str = None) -> FileCategory:
        """
        根据文件名和MIME类型确定文件类别
        
        Args:
            filename: 文件名
            mime_type: MIME类型
            
        Returns:
            FileCategory: 文件类别
        """
        # 首先尝试通过MIME类型判断
        if mime_type and mime_type in cls.MIME_TYPE_MAPPING:
            return cls.MIME_TYPE_MAPPING[mime_type]
        
        # 然后通过文件扩展名判断
        file_extension = os.path.splitext(filename)[1].lower()
        if file_extension in cls.EXTENSION_MAPPING:
            return cls.EXTENSION_MAPPING[file_extension]
        
        # 默认按文本文件处理
        return FileCategory.TEXT
    
    @classmethod
    def get_max_file_size(cls, filename: str, mime_type: str = None) -> int:
        """
        获取文件的最大允许大小（字节）
        
        Args:
            filename: 文件名
            mime_type: MIME类型
            
        Returns:
            int: 最大文件大小（字节）
        """
        category = cls.get_file_category(filename, mime_type)
        max_size_mb = cls.FILE_SIZE_LIMITS[category]
        return max_size_mb * 1024 * 1024  # 转换为字节
    
    @classmethod
    def validate_file_size(cls, filename: str, file_size: int, mime_type: str = None) -> Tuple[bool, str]:
        """
        验证文件大小是否符合限制
        
        Args:
            filename: 文件名
            file_size: 文件大小（字节）
            mime_type: MIME类型
            
        Returns:
            Tuple[bool, str]: (是否通过验证, 错误信息)
        """
        category = cls.get_file_category(filename, mime_type)
        max_size = cls.get_max_file_size(filename, mime_type)
        max_size_mb = cls.FILE_SIZE_LIMITS[category]
        
        if file_size > max_size:
            return False, f"文件大小超出限制。{category.value}文件最大允许{max_size_mb}MB，当前文件大小为{file_size / 1024 / 1024:.1f}MB"
        
        return True, ""
    
    @classmethod
    def get_supported_extensions(cls) -> Set[str]:
        """获取所有支持的文件扩展名"""
        return set(cls.EXTENSION_MAPPING.keys())
    
    @classmethod
    def get_supported_mime_types(cls) -> Set[str]:
        """获取所有支持的MIME类型"""
        return set(cls.MIME_TYPE_MAPPING.keys())
    
    @classmethod
    def is_supported_file(cls, filename: str, mime_type: str = None) -> bool:
        """
        检查文件是否被支持
        
        Args:
            filename: 文件名
            mime_type: MIME类型
            
        Returns:
            bool: 是否支持该文件
        """
        # 检查MIME类型
        if mime_type and mime_type in cls.MIME_TYPE_MAPPING:
            return True
        
        # 检查文件扩展名
        file_extension = os.path.splitext(filename)[1].lower()
        return file_extension in cls.EXTENSION_MAPPING

# ============================================================================
# 应用配置
# ============================================================================

class LoggingConfig(BaseModel):
    """日志配置"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: Optional[str] = None
    max_bytes: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5

class DeduplicationConfig(BaseModel):
    """去重配置"""
    enabled: bool = True
    literal_match_enabled: bool = True
    semantic_similarity_enabled: bool = True
    semantic_similarity_threshold: float = 0.85  # 提高语义相似度阈值，更严格的去重
    min_content_length: int = 30  # 提高最小内容长度，避免对短文本过度去重
    score_diff_threshold: float = 0.02  # 搜索结果分数差异阈值（2%）
    content_similarity_threshold: float = 0.9  # 内容相似度阈值（90%）

class PDFProcessorConfig(BaseModel):
    """PDF处理器配置"""
    enable_screenshot_description: bool = True  # 是否启用页面截图的图像理解
    screenshot_description_max_pages: int = 20  # 最大处理页数，避免大文档处理时间过长
    screenshot_dpi: int = 200  # 截图分辨率

class Config(BaseModel):
    """应用配置"""
    logging: LoggingConfig = LoggingConfig()
    deduplication: DeduplicationConfig = DeduplicationConfig()
    pdf_processor: PDFProcessorConfig = PDFProcessorConfig()
    
    @classmethod
    def load(cls) -> "Config":
        """加载配置"""
        return cls(
            logging=LoggingConfig(
                level=os.getenv("LOG_LEVEL", "INFO"),
                file_path=os.getenv("LOG_FILE_PATH", "logs/kosmos.log")
            ),
            deduplication=DeduplicationConfig(
                enabled=os.getenv("DEDUP_ENABLED", "true").lower() == "true",
                literal_match_enabled=os.getenv("DEDUP_LITERAL_ENABLED", "true").lower() == "true",
                semantic_similarity_enabled=os.getenv("DEDUP_SEMANTIC_ENABLED", "true").lower() == "true",
                semantic_similarity_threshold=float(os.getenv("DEDUP_SEMANTIC_THRESHOLD", "0.85")),
                min_content_length=int(os.getenv("DEDUP_MIN_LENGTH", "30")),
                score_diff_threshold=float(os.getenv("DEDUP_SCORE_DIFF_THRESHOLD", "0.02")),
                content_similarity_threshold=float(os.getenv("DEDUP_CONTENT_SIMILARITY_THRESHOLD", "0.9"))
            ),
            pdf_processor=PDFProcessorConfig(
                enable_screenshot_description=os.getenv("PDF_ENABLE_SCREENSHOT_DESCRIPTION", "true").lower() == "true",
                screenshot_description_max_pages=int(os.getenv("PDF_SCREENSHOT_DESCRIPTION_MAX_PAGES", "20")),
                screenshot_dpi=int(os.getenv("PDF_SCREENSHOT_DPI", "200"))
            )
        )

# 全局配置实例
config = Config.load()

def get_logger(name: str) -> logging.Logger:
    """获取配置好的logger"""
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        # 设置日志级别
        logger.setLevel(getattr(logging, config.logging.level.upper()))
        
        # 创建formatter
        formatter = logging.Formatter(config.logging.format)
        
        # 控制台handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # 文件handler（如果配置了文件路径）
        if config.logging.file_path:
            log_file = Path(config.logging.file_path)
            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            from logging.handlers import RotatingFileHandler
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=config.logging.max_bytes,
                backupCount=config.logging.backup_count
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
    
    return logger