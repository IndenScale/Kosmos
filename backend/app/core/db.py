from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from .config import settings

is_sqlite = settings.DATABASE_URL.startswith("sqlite")

connect_args = {}
if is_sqlite:
    # For SQLite, we need to allow the same connection to be used across
    # different threads and set a timeout to handle concurrent writes from workers.
    connect_args = {"check_same_thread": False, "timeout": 15} # 15 second timeout

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args
)

if is_sqlite:
    # Enable Write-Ahead Logging (WAL) mode for SQLite.
    # This provides much better concurrency by allowing readers to continue
    # while a writer is in progress.
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL;")
        finally:
            cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """
    FastAPI dependency to get a database session.
    Ensures the session is always closed after the request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()