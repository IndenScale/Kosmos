"""
API router for managing Assessment Frameworks and their Control Item Definitions.
This router layer is responsible for handling HTTP requests and responses,
and it delegates all business logic to the service layer.
"""
import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from ..database import get_db
from .. import services, schemas

router = APIRouter(
    prefix="/frameworks",
    tags=["Frameworks"]
)

# --- Standard CRUD Endpoints ---

@router.post("/", response_model=schemas.FrameworkResponse, status_code=201)
def create_framework(framework: schemas.FrameworkCreate, db: Session = Depends(get_db)):
    return services.create_framework(db=db, framework=framework)

@router.get("/", response_model=List[schemas.FrameworkResponse])
def list_frameworks(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return services.get_frameworks(db=db, skip=skip, limit=limit)

@router.get("/{framework_id}", response_model=schemas.FrameworkResponse)
def get_framework(framework_id: UUID, db: Session = Depends(get_db)):
    db_framework = services.get_framework_by_id(db=db, framework_id=framework_id)
    if db_framework is None:
        raise HTTPException(status_code=404, detail="Framework not found")
    return db_framework

@router.delete("/{framework_id}", status_code=204)
def delete_framework(framework_id: UUID, db: Session = Depends(get_db)):
    """
    Deletes a framework and all its associated control items.
    """
    deleted_count = services.delete_framework_by_id(db=db, framework_id=framework_id)
    if deleted_count == 0:
        raise HTTPException(status_code=404, detail="Framework not found")
    return

@router.post("/{framework_id}/control_items", response_model=schemas.ControlItemDefinitionResponse, status_code=201)
def add_control_item_to_framework(
    framework_id: UUID,
    control_item: schemas.ControlItemDefinitionCreate,
    db: Session = Depends(get_db)
):
    db_control_item = services.add_control_item(db=db, framework_id=framework_id, control_item=control_item)
    if db_control_item is None:
        raise HTTPException(status_code=404, detail=f"Framework with id {framework_id} not found")
    return db_control_item

@router.get("/{framework_id}/control_items", response_model=List[schemas.ControlItemDefinitionResponse])
def list_control_items_for_framework(framework_id: UUID, db: Session = Depends(get_db)):
    db_framework = services.get_framework_by_id(db=db, framework_id=framework_id)
    if db_framework is None:
        raise HTTPException(status_code=404, detail="Framework not found")
    return services.get_control_items_for_framework(db=db, framework_id=framework_id)

# --- Bulk Import Endpoints ---

@router.get("/import/template", response_class=FileResponse)
def download_import_template():
    """
    Downloads the template file (`assessment_specs.jsonl`) for bulk importing
    control item definitions.
    """
    # This path is relative to the project root where the app is run from.
    # A more robust solution might use absolute paths or a config variable.
    template_path = "Artifacts/assessment_specs.jsonl"
    if not os.path.exists(template_path):
        raise HTTPException(status_code=404, detail="Template file not found.")
    
    return FileResponse(
        path=template_path,
        filename="assessment_specs_template.jsonl",
        media_type="application/jsonl"
    )

@router.post("/{framework_id}/control_items/import", summary="Bulk Import Control Items")
def bulk_import_control_items(
    framework_id: UUID,
    file: UploadFile = File(..., description="A JSONL file with control item definitions."),
    db: Session = Depends(get_db)
):
    """
    Bulk creates control item definitions for a framework from a JSONL file upload.

    - The file must be in JSONL format.
    - Each line must be a JSON object.
    - Each object must contain 'id' (or 'display_id') and 'content' fields.
    - All other fields will be stored in the 'details' JSON blob.
    """
    if file.content_type not in ["application/jsonl", "application/octet-stream", "text/plain"]:
         raise HTTPException(status_code=415, detail="Unsupported file type. Please upload a .jsonl file.")

    try:
        count = services.create_control_items_from_jsonl(db=db, framework_id=framework_id, file=file.file)
        return {"message": f"Successfully imported {count} control items."}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")
