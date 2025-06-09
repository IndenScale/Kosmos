# app/db/database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base # 导入 declarative_base
# from models.user import Base


# 数据库文件路径
SQLALCHEMY_DATABASE_URL = "sqlite:///./db/kosmos.db"

# 2. 从 URL 中提取文件路径，并获取其所在的目录
db_file_path = SQLALCHEMY_DATABASE_URL.replace("sqlite:///", "")
db_directory = os.path.dirname(db_file_path)

# 3. 如果目录非空且不存在，则创建它
if db_directory and not os.path.exists(db_directory):
    os.makedirs(db_directory)
    print(f"数据库目录 '{db_directory}' 已创建。")

# 创建数据库引擎
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})

# 创建会话
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 定义 Base
Base = declarative_base()

# 创建数据库表
def create_tables():
    from app.models import user, knowledge_base, document, chunk
    Base.metadata.create_all(bind=engine)

# 获取数据库会话
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()