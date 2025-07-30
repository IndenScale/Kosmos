from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

class ProcessorLogEntry(BaseModel):
    timestamp: datetime
    level: LogLevel
    message: str
    processor_type: str
    file_path: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        use_enum_values = True