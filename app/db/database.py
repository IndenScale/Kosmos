from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.user import Base
import os

# 数据库文件路径
DATABASE_URL = "sqlite:///./data/db/kosmos.db"

# 创建数据库引擎
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# 创建会话
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建数据库表
def create_tables():
    Base.metadata.create_all(bind=engine)

# 获取数据库会话
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()