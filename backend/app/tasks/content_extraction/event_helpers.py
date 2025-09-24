# backend/app/tasks/content_extraction/event_helpers.py
import json
from typing import Dict, Any
from sqlalchemy.orm import Session

from ...models import Job, DomainEvent
from ...models.domain_events.ingestion_events import DocumentContentExtractedPayload

def create_document_content_extracted_event(db: Session, job: Job, pipeline_result: Dict[str, Any]):
    """
    Creates and stages a DocumentContentExtracted domain event.
    """
    doc = job.document
    
    # Filter out None asset IDs to prevent validation errors
    assets = pipeline_result.get("assets", [])
    extracted_asset_ids = [asset.id for asset in assets if asset and asset.id is not None]
    
    # Build the payload dictionary, ensuring optional fields are present, even if None.
    payload_data = {
        "document_id": doc.id,
        "knowledge_space_id": doc.knowledge_space_id,
        "initiator_id": job.initiator_id,
        "extracted_asset_ids": extracted_asset_ids,
        "canonical_content_id": pipeline_result["canonical_content"].id,
        "libre_office_record": pipeline_result.get("libre_office_record"),
        "mineru_record": pipeline_result.get("mineru_record"),
    }

    # This warning is now more accurate.
    if not payload_data["mineru_record"]:
        print(f"[WARNING] mineru_record is None for document {doc.id}. It will be set to None in the event payload.")

    payload = DocumentContentExtractedPayload(**payload_data)

    try:
        payload_json_str = payload.model_dump_json(exclude_none=True)
    except AttributeError:
        payload_json_str = payload.json(exclude_none=True)

    # Store as JSON string to match DomainEvent.payload field type (Text)
    domain_event = DomainEvent(
        aggregate_id=str(doc.id),
        event_type="DocumentContentExtractedPayload",
        payload=payload_json_str,
    )
    db.add(domain_event)
    print(f"  - Staged event 'DocumentContentExtracted' for document {doc.id}")
