from sqlalchemy import TypeDecorator, String
from sqlalchemy.orm import declarative_base
import uuid


class UUIDChar(TypeDecorator):
    """
    A custom SQLAlchemy type that stores UUIDs as strings in the database.
    This provides compatibility across different database backends while maintaining
    UUID functionality in Python code.
    """
    impl = String(36)  # UUID string length is 36 characters
    cache_ok = True
    
    def process_bind_param(self, value, dialect):
        """Convert UUID to string when storing in database"""
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return str(value)
        if isinstance(value, str):
            # Validate that it's a proper UUID string
            try:
                uuid.UUID(value)
                return value
            except ValueError:
                raise ValueError(f"Invalid UUID string: {value}")
        raise TypeError(f"Expected UUID or string, got {type(value)}")
    
    def process_result_value(self, value, dialect):
        """Convert string back to UUID when loading from database"""
        if value is None:
            return None
        if isinstance(value, str):
            return uuid.UUID(value)
        return value


# Create a shared Base for all models to inherit from
Base = declarative_base()