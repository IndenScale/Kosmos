from abc import ABC, abstractmethod
from typing import Tuple, List, Dict, Any
from pathlib import Path
from datetime import datetime
from app.config import get_logger
from app.schemas.processor_log import ProcessorLogEntry

class BaseProcessor(ABC):
    """文档处理器基类"""
    
    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)
    
    @abstractmethod
    def can_process(self, file_path: str) -> bool:
        """判断是否可以处理该文件类型"""
        pass
    
    @abstractmethod
    def _extract_content_impl(self, file_path: str) -> Tuple[str, List[str]]:
        """提取文档内容的具体实现
        
        Returns:
            Tuple[str, List[str]]: (markdown_text, image_paths)
        """
        pass
    
    def needs_screenshot(self, file_path: str) -> bool:
        """判断是否需要生成截图
        
        默认返回False，只有需要截图的处理器（如PDF、PPT等）才重写此方法返回True
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 是否需要生成截图
        """
        return False
    
    def extract_content(self, file_path: str) -> Tuple[str, List[str]]:
        """提取文档内容（带日志记录）
        
        Returns:
            Tuple[str, List[str]]: (markdown_text, image_paths)
        """
        start_time = datetime.now()
        processor_type = self.__class__.__name__
        
        # 创建日志条目
        log_entry = ProcessorLogEntry(
            processor_type=processor_type,
            file_path=file_path,
            start_time=start_time,
            success=False
        )
        
        self.logger.info(f"开始处理文件: {file_path}, 处理器: {processor_type}")
        
        try:
            # 调用具体实现
            markdown_text, image_paths = self._extract_content_impl(file_path)
            
            # 更新日志条目
            end_time = datetime.now()
            processing_duration = int((end_time - start_time).total_seconds() * 1000)
            
            log_entry.end_time = end_time
            log_entry.success = True
            log_entry.markdown_text_length = len(markdown_text) if markdown_text else 0
            log_entry.image_count = len(image_paths)
            log_entry.image_paths = image_paths
            log_entry.processing_duration_ms = processing_duration
            
            self.logger.info(
                f"文件处理成功: {file_path}, "
                f"耗时: {processing_duration}ms, "
                f"文本长度: {log_entry.markdown_text_length}, "
                f"图片数量: {log_entry.image_count}"
            )
            
            return markdown_text, image_paths
            
        except Exception as e:
            # 记录错误
            end_time = datetime.now()
            processing_duration = int((end_time - start_time).total_seconds() * 1000)
            
            log_entry.end_time = end_time
            log_entry.success = False
            log_entry.error_message = str(e)
            log_entry.processing_duration_ms = processing_duration
            
            self.logger.error(
                f"文件处理失败: {file_path}, "
                f"耗时: {processing_duration}ms, "
                f"错误: {str(e)}"
            )
            
            raise
        
        finally:
            # 记录详细日志（可选：存储到数据库或文件）
            self._log_processing_details(log_entry)
    
    def _log_processing_details(self, log_entry: ProcessorLogEntry):
        """记录处理详情（子类可重写以自定义日志存储）"""
        self.logger.debug(f"处理详情: {log_entry.model_dump_json()}")
    
    def get_supported_extensions(self) -> List[str]:
        return []