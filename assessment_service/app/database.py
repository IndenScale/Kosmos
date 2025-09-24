"""
Database session management for the Assessment Service.

This module sets up the SQLAlchemy engine and session handling. It provides a
dependency that can be injected into FastAPI routes to get a database session.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv(dotenv_path="../.env")

# Get the database URL from environment variables, with a fallback for SQLite
DATABASE_URL = os.getenv("ASSESSMENT_DATABASE_URL", "sqlite:///./assessment.db")

# The connect_args are specific to SQLite and are needed to allow multithreading,
# which is relevant for FastAPI's async nature.
engine_args = {}
if DATABASE_URL.startswith("sqlite"):
    engine_args["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_args)

# SessionLocal is a factory for creating new Session objects
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """
    FastAPI dependency to get a DB session.
    Ensures the database session is always closed after the request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
