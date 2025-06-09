from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from db.database import create_tables
from routers import auth, knowledge_bases, documents, ingestion, search

# 创建FastAPI应用
app = FastAPI(
    title="Kosmos API",
    description="Knowledge Management System API",
    version="1.0.0"
)

# 使用 on_event 装饰器注册启动事件
@app.on_event("startup")
def on_startup():
    print("应用启动，开始创建数据库表...")
    create_tables()
    print("数据库表检查/创建完成。")

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该限制具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 包含路由
app.include_router(auth.router)
app.include_router(knowledge_bases.router)
app.include_router(documents.router)
app.include_router(ingestion.router)
app.include_router(search.router)  # 添加搜索路由
@app.get("/")
def read_root():
    return {"message": "Welcome to Kosmos API"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}