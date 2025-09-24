import dramatiq
import uuid
import logging
import os
import time
import random
from datetime import datetime
from sqlalchemy.exc import OperationalError
from backend.app.models import Chunk
from . import helpers, prompts, validators
from .helpers import build_llm_context
from .event_helpers import create_document_chunking_completed_event

print("--- [Actor Probe] chunking.actor module loaded ---")

logger = logging.getLogger(__name__)

LINES_PER_BATCH = 200

def setup_trace_logger(job_id: str) -> logging.Logger:
    trace_logger = logging.getLogger(f"chunking_trace.{job_id}")
    trace_logger.setLevel(logging.INFO)
    trace_logger.propagate = False
    if not trace_logger.handlers:
        log_dir = "logs/dramatiq_actor/chunking"
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"chunking_trace_{job_id}.log")
        handler = logging.FileHandler(log_file, mode='a')
        formatter = logging.Formatter('%(asctime)s\n%(message)s\n')
        handler.setFormatter(formatter)
        trace_logger.addHandler(handler)
    return trace_logger

from backend.app.tasks.service_factory import get_services_scope
from backend.app.models import JobStatus

@dramatiq.actor(
    queue_name="chunking",
    max_retries=5, 
    time_limit=604_800_000
)
def chunk_document_actor(job_id: str):
    from backend.app.tasks.service_factory import get_services_scope
    job_uuid = uuid.UUID(job_id)
    logger.info(f"Job {job_uuid}: --- Chunking Actor started ---")
    trace_logger = setup_trace_logger(job_id)
    
    with get_services_scope() as services:
        job_service = services["job_service"]
        try:
            ai_provider_service = services["ai_provider_service"]
            reading_service = services["reading_service"]
            db = services["db"]

            job = job_service.start_job(job_uuid)

            # Idempotency: Clear existing chunks
            existing_chunks = db.query(Chunk).filter(Chunk.document_id == job.document_id).all()
            if existing_chunks:
                logger.warning(f"Job {job_uuid}: Deleting {len(existing_chunks)} existing chunks.")
                for chunk in existing_chunks:
                    db.delete(chunk)
                # A commit here is acceptable as it's part of the setup phase.
                db.commit()

            llm_client = ai_provider_service.get_client_for_chunking(user_id=job.initiator_id, knowledge_space_id=job.knowledge_space_id)
            current_line = 1
            total_lines = 0

            while True:
                if total_lines > 0 and current_line > total_lines:
                    break

                content_data = reading_service.read_document_content(document_id=job.document_id, start=current_line, max_lines=LINES_PER_BATCH, preserve_integrity=True)
                megachunk_text = "\n".join(line['content'] for line in content_data.get("lines", []))
                
                if total_lines == 0:
                    total_lines = content_data.get("total_lines", 0)
                    job_service.update_progress(job, "chunking_started", f"Total lines: {total_lines}", total_lines=total_lines)

                if not megachunk_text.strip():
                    break

                is_final_batch = (current_line + LINES_PER_BATCH >= total_lines)
                
                # 默认使用基于规则的分割器以提高性能，可以通过 job context 覆盖
                chunking_params = job.context.get("chunking_params", {})
                splitter_type = chunking_params.get("splitter", "rule_based")
                
                trace_logger.info(f"Processing megachunk: start_line={current_line}, size={len(megachunk_text.splitlines())}, final={is_final_batch}, splitter={splitter_type}")
                
                if splitter_type == "rule_based":
                    last_processed_line, _ = helpers.split_megachunk_with_rules(db, job, megachunk_text.splitlines(), current_line, trace_logger, llm_client)
                else:
                    last_processed_line, _ = helpers.split_megachunk_with_llm(db, job, llm_client, megachunk_text.splitlines(), current_line, trace_logger, is_final_batch)
                
                current_line = last_processed_line + 1
                
                if is_final_batch:
                    break

                job_service.update_progress(job, "chunking", f"Processed up to line {current_line}", current_line=current_line)
                # Intermediate commits can be useful for long-running jobs to save progress.
                db.commit()

            final_chunk_count = db.query(Chunk).filter(Chunk.document_id == job.document_id).count()
            
            # 创建分块完成领域事件
            chunking_result = {
                "start_time": job.created_at,
                "end_time": datetime.utcnow(),
                "total_lines": total_lines,
                "chunks_created": final_chunk_count
            }
            
            print("  - Creating 'DocumentChunkingCompleted' domain event...")
            create_document_chunking_completed_event(db, job, chunking_result)
            
            result = {"chunks_created": final_chunk_count}
            job_service.finalize_job(job_uuid, status=JobStatus.COMPLETED, result=result)
            db.commit()
            logger.info(f"Job {job_uuid}: --- Job COMPLETED successfully ---")

        except Exception as e:
            logger.error(f"Job {job_uuid}: An unhandled exception occurred: {e}", exc_info=True)
            job_service.finalize_job(job_uuid, status=JobStatus.FAILED, error_message=str(e))
            db.commit()
            raise


