import logging
import os
from pathlib import Path
from pydantic import BaseModel
from typing import Optional

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