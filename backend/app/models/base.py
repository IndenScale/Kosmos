import uuid
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import CHAR
from sqlalchemy.types import TypeDecorator

Base = declarative_base()

# 自定义UUID类型，用于处理SQLite中的UUID存储
class UUIDChar(TypeDecorator):
    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """在数据发送到数据库时被调用"""
        if value is None:
            return value
        elif isinstance(value, uuid.UUID):
            return str(value)
        else:
            return value

    def process_result_value(self, value, dialect):
        """在从数据库读取数据时被调用"""
        if value is None:
            return value
        else:
            try:
                return uuid.UUID(value)
            except (TypeError, ValueError):
                return value
