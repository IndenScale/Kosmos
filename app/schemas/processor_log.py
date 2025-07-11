from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional

class ProcessorLogEntry(BaseModel):
    """处理器日志条目"""
    processor_type: str = Field(..., description="处理器类型")
    file_path: str = Field(..., description="处理的文件路径")
    start_time: datetime = Field(..., description="处理开始时间")
    end_time: Optional[datetime] = Field(None, description="处理结束时间")
    success: bool = Field(..., description="处理是否成功")
    markdown_text_length: Optional[int] = Field(None, description="生成的markdown文本长度")
    image_count: int = Field(0, description="提取的图片数量")
    image_paths: List[str] = Field(default_factory=list, description="图片路径列表")
    error_message: Optional[str] = Field(None, description="错误信息")
    processing_duration_ms: Optional[int] = Field(None, description="处理耗时（毫秒）")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }