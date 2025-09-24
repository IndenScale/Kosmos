"""
Main FastAPI application for the Assessment Service.

This service orchestrates the assessment workflow, manages assessment
frameworks, jobs, and sessions.
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Internal modules
from .database import engine
from .models import Base
from .routers import frameworks, jobs, sessions, agent_actions, execution, requeue, findings # Import the new router
from . import broker # Ensure Dramatiq broker is initialized

# --- App Initialization ---

# Create all database tables on startup based on the shared Base
Base.metadata.create_all(bind=engine)

load_dotenv(dotenv_path="../.env")

app = FastAPI(
    title="Kosmos Assessment Service",
    description="A service to manage assessment frameworks, jobs, and the overall assessment workflow.",
    version="2.0.0" # Version bump to reflect the major refactoring
)

# --- CORS Configuration ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源，生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有HTTP方法
    allow_headers=["*"],  # 允许所有请求头
)

# --- API Router Definition ---

# Include the new routers
app.include_router(frameworks.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")
app.include_router(sessions.router, prefix="/api/v1")
app.include_router(agent_actions.router, prefix="/api/v1")
app.include_router(execution.router, prefix="/api/v1")
app.include_router(requeue.router, prefix="/api/v1")
app.include_router(findings.router, prefix="/api/v1")

# TODO: Add routers for jobs and sessions next.

# --- Root Endpoint ---

@app.get("/")
def read_root():
    return {"service": "Kosmos Assessment Service", "status": "running", "version": "2.0.0"}

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("ASSESSMENT_APP_HOST", "127.0.0.1")
    port = int(os.getenv("ASSESSMENT_APP_PORT", 8015))
    uvicorn.run(app, host=host, port=port)
