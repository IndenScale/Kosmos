from fastapi import FastAPI
from sqlalchemy import text, inspect
from .core.logging_config import setup_logging
from .core.object_storage import ensure_buckets_exist
from .core.db import engine
from .core.config import settings  # Import settings

# Import the Base object and all models to ensure they are registered with SQLAlchemy's metadata
from .models import Base
import backend.app.models


# Set up logging as the first step
setup_logging()

def create_tables():
    """
    Creates all database tables based on the current models.
    This is a non-destructive operation: it only creates tables that do not already exist.
    """
    print("Ensuring all database tables exist...")
    Base.metadata.create_all(bind=engine)
    print("Database tables checked.")

def setup_fts():
    """
    Sets up the SQLite FTS5 virtual table for full-text search on chunks.
    This function is idempotent.
    """
    print("Checking FTS setup for chunks...")
    
    CREATE_FTS_TABLE_SQL = """
    CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
        chunk_id UNINDEXED,
        raw_content,
        summary,
        paraphrase,
        tokenize = 'porter unicode61'
    );
    """
    
    # Triggers to keep the FTS table in sync with the main chunks table
    CREATE_INSERT_TRIGGER_SQL = """
    CREATE TRIGGER IF NOT EXISTS chunks_after_insert
    AFTER INSERT ON chunks
    BEGIN
        INSERT INTO chunks_fts (chunk_id, raw_content, summary, paraphrase)
        VALUES (new.id, new.raw_content, new.summary, new.paraphrase);
    END;
    """
    CREATE_DELETE_TRIGGER_SQL = """
    CREATE TRIGGER IF NOT EXISTS chunks_after_delete
    AFTER DELETE ON chunks
    BEGIN
        DELETE FROM chunks_fts WHERE chunk_id = old.id;
    END;
    """
    CREATE_UPDATE_TRIGGER_SQL = """
    CREATE TRIGGER IF NOT EXISTS chunks_after_update
    AFTER UPDATE ON chunks
    BEGIN
        DELETE FROM chunks_fts WHERE chunk_id = old.id;
        INSERT INTO chunks_fts (chunk_id, raw_content, summary, paraphrase)
        VALUES (new.id, new.raw_content, new.summary, new.paraphrase);
    END;
    """
    
    # SQL to populate the FTS table with any data that might be missing
    POPULATE_FTS_TABLE_SQL = """
    INSERT INTO chunks_fts (chunk_id, raw_content, summary, paraphrase)
    SELECT id, raw_content, summary, paraphrase FROM chunks
    WHERE id NOT IN (SELECT chunk_id FROM chunks_fts);
    """

    with engine.connect() as connection:
        trans = connection.begin()
        try:
            inspector = inspect(engine)
            if 'chunks_fts' not in inspector.get_table_names():
                print("Creating 'chunks_fts' virtual table...")
                connection.execute(text(CREATE_FTS_TABLE_SQL))
            
            print("Ensuring FTS synchronization triggers exist...")
            connection.execute(text(CREATE_INSERT_TRIGGER_SQL))
            connection.execute(text(CREATE_DELETE_TRIGGER_SQL))
            connection.execute(text(CREATE_UPDATE_TRIGGER_SQL))
            
            print("Populating FTS table with any missing data...")
            result = connection.execute(text(POPULATE_FTS_TABLE_SQL))
            if result.rowcount > 0:
                print(f"Added {result.rowcount} new rows to the FTS index.")
            
            trans.commit()
            print("FTS setup check complete.")
        except Exception as e:
            print(f"An error occurred during FTS setup: {e}")
            trans.rollback()

app = FastAPI(
    title="Kosmos Knowledge Management Platform",
    description="Backend services for the Kosmos platform.",
    version="0.1.0"
)

@app.on_event("startup")
def on_startup():
    """
    Actions to perform on application startup.
    """
    print("Application is starting up...")
    
    # 1. Ensure database tables are created
    create_tables()

    # 2. Set up Full-Text Search if using SQLite
    if engine.dialect.name == 'sqlite':
        setup_fts()

    # 3. Ensure Minio buckets exist
    try:
        ensure_buckets_exist()
    except Exception as e:
        print(f"Could not connect to Minio or create buckets on startup: {e}")
        # Handle the error appropriately, e.g., exit the application
        # For now, we just print the error.
    print("Startup actions finished.")


@app.get("/", tags=["Root"])
def read_root():
    """
    A simple health check endpoint.
    """
    return {"status": "ok", "message": "Welcome to Kosmos Backend!"}

# In the future, routers will be included here
from .routers import (
    auth, users, knowledge_spaces, documents, assets, credentials, jobs,
    search, chunks, knowledge_space_config, knowledge_space_credentials,
    bookmarks, contents, grep, read, ingestion, domain_events,
    document_ingestion_status
)
# app.include_router(documents.router)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(knowledge_spaces.router, prefix="/api/v1/knowledge-spaces", tags=["Knowledge Spaces"])
app.include_router(knowledge_space_config.router) # This router has its own prefix and tags
app.include_router(knowledge_space_credentials.router, prefix="/api/v1/knowledge-spaces") # This router has its own prefix and tags
app.include_router(documents.router, prefix="/api/v1/documents", tags=["Documents"])
app.include_router(ingestion.router, prefix="/api/v1/ingest", tags=["Ingestion"])
app.include_router(domain_events.router, prefix="/api/v1/events", tags=["Domain Events"])
app.include_router(contents.router, prefix="/api/v1/contents", tags=["Contents"])
app.include_router(chunks.router, prefix="/api/v1/chunks", tags=["Chunks"])
app.include_router(assets.router, prefix="/api/v1/assets", tags=["Assets"])
app.include_router(bookmarks.router, prefix="/api/v1/bookmarks", tags=["Bookmarks"])
app.include_router(credentials.router, prefix="/api/v1/credentials", tags=["Credentials"])
app.include_router(jobs.router, prefix="/api/v1", tags=["Jobs"])
app.include_router(search.router, prefix="/api/v1/search", tags=["Search"])
app.include_router(grep.router, prefix="/api/v1/grep", tags=["Grep"])
app.include_router(read.router, prefix="/api/v1/read", tags=["Read"])
app.include_router(document_ingestion_status.router, prefix="/api/v1/knowledge-spaces", tags=["Document Ingestion Status"])
