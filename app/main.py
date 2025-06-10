import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.database import Base, create_tables
from app.routers import auth, knowledge_bases, documents, ingestion, search
from app.utils.task_queue import task_queue

import app.models.user
import app.models.knowledge_base
import app.models.document
import app.models.chunk

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("应用启动，开始创建数据库表...")
    create_tables()
    print("数据库表检查/创建完成。")
    await task_queue.start()
    print("异步任务队列已启动")
    yield

    # 关闭时运行
    await task_queue.stop()
    print("异步任务队列已停止")

# 创建FastAPI应用
app = FastAPI(
    title="Kosmos API",
    description="Knowledge Management System API",
    version="1.0.0",
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
app.include_router(knowledge_bases.router)
app.include_router(documents.router)
app.include_router(ingestion.router)
app.include_router(search.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to Kosmos API"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}
