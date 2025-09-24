"""
Service layer for handling business logic related to Assessment Frameworks.

This layer separates the database operations from the API/router layer,
making the code cleaner, more testable, and easier to maintain.
"""
import json
from sqlalchemy.orm import Session
from typing import List, Optional, IO
from uuid import UUID

from .. import models, schemas

def create_framework(db: Session, framework: schemas.FrameworkCreate) -> models.AssessmentFramework:
    """
    Creates a new assessment framework in the database.
    """
    db_framework = models.AssessmentFramework(**framework.dict())
    db.add(db_framework)
    db.commit()
    db.refresh(db_framework)
    return db_framework

def get_frameworks(db: Session, skip: int = 0, limit: int = 100) -> List[models.AssessmentFramework]:
    """
    Retrieves a list of all assessment frameworks.
    """
    return db.query(models.AssessmentFramework).offset(skip).limit(limit).all()

def get_framework_by_id(db: Session, framework_id: UUID) -> Optional[models.AssessmentFramework]:
    """
    Retrieves a single assessment framework by its ID.
    """
    return db.query(models.AssessmentFramework).filter(models.AssessmentFramework.id == framework_id).first()

def delete_framework_by_id(db: Session, framework_id: UUID) -> int:
    """
    Deletes a framework by its ID.
    Returns the number of rows deleted.
    """
    num_deleted = db.query(models.AssessmentFramework).filter(models.AssessmentFramework.id == framework_id).delete()
    db.commit()
    return num_deleted

def add_control_item(
    db: Session,
    framework_id: UUID,
    control_item: schemas.ControlItemDefinitionCreate
) -> Optional[models.ControlItemDefinition]:
    """
    Adds a new control item definition to a framework.
    Returns the new control item, or None if the framework does not exist.
    """
    framework = get_framework_by_id(db, framework_id)
    if not framework:
        return None
        
    db_control_item = models.ControlItemDefinition(
        **control_item.dict(),
        framework_id=framework_id
    )
    db.add(db_control_item)
    db.commit()
    db.refresh(db_control_item)
    return db_control_item

def get_control_items_for_framework(db: Session, framework_id: UUID) -> List[models.ControlItemDefinition]:
    """
    Retrieves all control item definitions for a specific framework.
    """
    return db.query(models.ControlItemDefinition).filter(models.ControlItemDefinition.framework_id == framework_id).all()

def create_control_items_from_jsonl(db: Session, framework_id: UUID, file: IO[bytes]) -> int:
    """
    Parses a JSONL file and bulk-creates control item definitions for a framework.
    
    Returns the number of items successfully created.
    """
    framework = get_framework_by_id(db, framework_id)
    if not framework:
        raise ValueError(f"Framework with id {framework_id} not found.")

    items_to_create = []
    for line in file:
        try:
            data = json.loads(line)
            
            display_id = data.pop('id', data.pop('display_id', None))
            content = data.pop('content', None)

            if not display_id or not content:
                # Skip lines that are missing essential fields
                continue

            # The rest of the data goes into the 'details' field
            details = data

            item_schema = schemas.ControlItemDefinitionCreate(
                display_id=display_id,
                content=content,
                details=details
            )
            
            items_to_create.append(models.ControlItemDefinition(
                **item_schema.dict(),
                framework_id=framework_id
            ))
        except (json.JSONDecodeError, KeyError):
            # Skip malformed lines
            continue
    
    if not items_to_create:
        return 0

    db.bulk_save_objects(items_to_create)
    db.commit()
    
    return len(items_to_create)
