import dramatiq
import uuid
import time
import os
from dotenv import load_dotenv

# --- [CRITICAL FIX] Explicitly load .env to ensure worker has correct config ---
# This guarantees the worker connects to the same database as the trigger and API,
# resolving the "job not found" issue caused by inconsistent configuration loading.
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path, override=True)
# --- End of Fix ---

from . import pipelines
from .event_helpers import create_document_content_extracted_event
from backend.app.models import JobStatus, Job, Document
from backend.app.services.job.exceptions import JobNotFoundError
from backend.app.tasks.service_factory import get_services_scope

print("--- [Actor Probe] content_extraction.actor module loaded ---")

@dramatiq.actor(
    queue_name="content_extraction",
    max_retries=3,
    min_backoff=5000,  # Increased backoff to 5 seconds
    time_limit=3600_000 # 1 hour time limit
)
def content_extraction_actor(job_id: str):
    """
    The primary actor responsible for the content extraction phase.
    It orchestrates the use of tools like LibreOffice and MinerU.
    """
    print(f"DEBUG PROBE: Actor received job_id: {job_id}. Attempting to start processing.")
    
    # --- [REVISED LOCKING STRATEGY] ---
    # The entire process will be managed within a single service scope to ensure
    # consistent session handling. We will manually commit the initial "RUNNING"
    # state update to release the lock before starting the long-running task.
    
    job = None
    pipeline_result = None
    
    with get_services_scope() as services:
        job_service = services["job_service"]
        db = job_service.db

        try:
            # Phase 1: Claim the job and commit immediately.
            try:
                job = job_service.start_job(job_id)
                db.commit()
                print(f"--- [Content Extraction Actor] Job {job_id} successfully marked as RUNNING and committed. ---")
            except Exception as e:
                db.rollback()
                print(f"  - ERROR: Failed to mark job {job_id} as RUNNING. It may have been picked up by another worker. Error: {e}")
                raise

            # Phase 2: Long-running processing (outside any active DB transaction).
            # We now have the job object and can proceed.
            doc = job.document
            if not doc:
                raise ValueError(f"Job '{job_id}' found, but its associated Document (ID: {job.document_id}) could NOT be found.")

            print(f"  - Job details loaded. Processing document_id: {doc.id}")
            mime_type = doc.original.detected_mime_type
            print(f"  - Document MIME type: {mime_type}")

            OFFICE_MIME_TYPES = {
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                "application/msword", "application/vnd.ms-excel", "application/vnd.ms-powerpoint",
                "application/vnd.visio", "application/rtf", "text/rtf"
            }

            if mime_type.startswith('text/'):
                print("  - Routing to: Text Pipeline")
                pipeline_result = pipelines.run_text_pipeline(job, job_service)
            elif mime_type.startswith('image/'):
                print("  - Routing to: Image Pipeline")
                pipeline_result = pipelines.run_image_pipeline(job, job_service)
            elif mime_type == 'application/pdf':
                print("  - Routing to: PDF Pipeline")
                pipeline_result = pipelines.run_pdf_pipeline(job, job_service)
            elif mime_type in OFFICE_MIME_TYPES:
                print("  - Routing to: Office Pipeline")
                override_path = job.context.get('modified_docx_path') if job.context else None
                pipeline_result = pipelines.run_office_pipeline(job, job_service, override_storage_path=override_path)
            else:
                print(f"  - Skipping unsupported MIME type: {mime_type}")
                result = {"status": "skipped", "reason": f"Unsupported MIME type: {mime_type}"}
                job_service.finalize_job(job.id, status=JobStatus.COMPLETED, result=result)
                db.commit()
                print(f"--- [Content Extraction Actor] Job {job_id} COMPLETED (Skipped) ---")
                return

            if pipeline_result is None:
                print(f"  - Pipeline processing halted intentionally. Acknowledging message.")
                print(f"--- [Content Extraction Actor] Job {job_id} HALTED ---")
                return

            # Phase 3: Finalize the job within the same session.
            canonical_content_id = pipeline_result["canonical_content"].id

            existing_doc = db.query(Document).filter(
                Document.knowledge_space_id == doc.knowledge_space_id,
                Document.canonical_content_id == canonical_content_id,
                Document.id != doc.id
            ).first()

            if existing_doc:
                print(f"  - DUPLICATE DETECTED: Doc {doc.id} has same canonical content as existing doc {existing_doc.id}.")
                doc.status = "archived_as_duplicate"
                result = {
                    "status": "processed_as_duplicate",
                    "reason": f"Canonical content is identical to existing document {existing_doc.id}",
                    "canonical_content_id": str(canonical_content_id)
                }
                job_service.finalize_job(job.id, status=JobStatus.COMPLETED, result=result)
                db.commit()
                print(f"--- [Content Extraction Actor] Job {job_id} COMPLETED (Processed as duplicate) ---")
                return

            print("  - Pipeline execution completed successfully.")
            doc.canonical_content_id = canonical_content_id
            doc.status = "processed"

            print("  - Creating 'DocumentContentExtracted' domain event...")
            create_document_content_extracted_event(db, job, pipeline_result)

            result = {
                "canonical_content_id": str(canonical_content_id),
                "asset_count": len(pipeline_result.get("assets", []))
            }

            print("  - Finalizing job as COMPLETED.")
            job_service.finalize_job(job.id, status=JobStatus.COMPLETED, result=result)
            db.commit()
            print(f"--- [Content Extraction Actor] Job {job_id} COMPLETED successfully ---")

        except Exception as e:
            db.rollback()
            doc_id_str = f"for document {job.document.id}" if job and hasattr(job, 'document') and job.document else ""
            print(f"  - ERROR: An exception occurred while processing job {job_id} {doc_id_str}: {e}")
            
            # Use a new session scope to finalize the job to avoid session state issues.
            with get_services_scope() as finalization_services:
                finalization_job_service = finalization_services["job_service"]
                job_id_to_finalize = job.id if job else job_id
                try:
                    finalization_job_service.finalize_job(job_id_to_finalize, status=JobStatus.FAILED, error_message=str(e))
                    finalization_services["db"].commit()
                    print(f"--- [Content Extraction Actor] Job {job_id} FAILED and status updated. ---")
                except Exception as final_e:
                    print(f"  - CRITICAL ERROR: Failed to even mark job {job_id} as FAILED. Error: {final_e}")
                    finalization_services["db"].rollback()
            raise