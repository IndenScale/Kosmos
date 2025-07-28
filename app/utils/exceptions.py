"""
自定义异常类
文件: exceptions.py
创建时间: 2025-07-26
描述: 定义应用程序中使用的自定义异常
"""


class ValidationError(Exception):
    """验证错误异常"""

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class ProcessingError(Exception):
    """处理错误异常"""

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class ParsingError(Exception):
    """解析错误异常"""

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class ConfigurationError(Exception):
    """配置错误异常"""

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)