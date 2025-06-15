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

class Config(BaseModel):
    """应用配置"""
    logging: LoggingConfig = LoggingConfig()
    
    @classmethod
    def load(cls) -> "Config":
        """加载配置"""
        return cls(
            logging=LoggingConfig(
                level=os.getenv("LOG_LEVEL", "INFO"),
                file_path=os.getenv("LOG_FILE_PATH", "logs/kosmos.log")
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