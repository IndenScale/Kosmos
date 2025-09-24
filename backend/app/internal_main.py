from fastapi import FastAPI, Depends
from .core.logging_config import setup_logging
from .routers import assets_admin, originals_admin, documents_admin, canonical_contents_admin
from .internal_dependencies import get_internal_api_key

# Set up logging as the first step
setup_logging()

internal_app = FastAPI(
    title="Kosmos Internal API",
    description="Internal services for workers, administration, and system health checks.",
    version="0.1.0",
)

@internal_app.get("/", tags=["Root"])
def read_root():
    """
    A simple health check endpoint for the internal API.
    """
    return {"status": "ok", "message": "Welcome to Kosmos Internal API!"}

# Include internal routers
internal_app.include_router(assets_admin.router, prefix="/api/v1/admin/assets", tags=["Admin - Assets"])
internal_app.include_router(originals_admin.router, prefix="/api/v1/admin/originals", tags=["Admin - Originals"])
internal_app.include_router(documents_admin.router, prefix="/api/v1/admin/documents", tags=["Admin - Documents"])
internal_app.include_router(canonical_contents_admin.router, prefix="/api/v1/admin/canonical-contents", tags=["Admin - Canonical Contents"])
