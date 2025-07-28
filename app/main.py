import os
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.database import Base, create_tables
from app.routers import auth
from app.routers import users
from app.routers import knowledge_bases
from app.routers import documents
from app.routers import credentials
from app.routers import fragments
from app.routers import parser
from app.routers import index
from app.routers import search
from app.routers import jobs
# from app.routers import knowledge_bases, documents
from app.services.unified_job_service import unified_job_service

# Find the project root by looking for the .env file
from pathlib import Path

# Construct the path to the .env file.
# This assumes the .env file is in the project root, two levels up from main.py
dotenv_path = Path(__file__).parent.parent / '.env'

# Load the .env file from the specified path
load_dotenv(dotenv_path=dotenv_path)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("应用启动，开始创建数据库表...")
    create_tables()
    print("数据库表检查/创建完成。")
    await unified_job_service.start()
    print("统一任务服务已启动")
    yield

    # 关闭时运行
    await unified_job_service.stop()
    print("统一任务服务已停止")

# 创建FastAPI应用
app = FastAPI(
    title="Kosmos API",
    description="Knowledge Management System API",
    version="2.0.0",
    lifespan=lifespan
)

# 从环境变量获取前端URL
WEBUI_URL = os.getenv("WEBUI_URL", "http://localhost:3000")

# 配置允许的源
allowed_origins = [
    WEBUI_URL,
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://10.19.8.199:3000",  # 如果前端部署在这个IP
]

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# 包含路由
app.include_router(auth.router)

app.include_router(users.router)
app.include_router(knowledge_bases.router)
app.include_router(documents.router)
app.include_router(credentials.router)
app.include_router(fragments.router)
app.include_router(parser.router)
app.include_router(index.router)
app.include_router(search.router)
app.include_router(jobs.router)
# app.include_router(ingestion.router)
# app.include_router(sdtm.router)
# app.include_router(tagging.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to Kosmos API"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}
