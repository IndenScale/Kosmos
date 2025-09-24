import dramatiq
import uuid
import logging
import openai
from typing import List
from sqlalchemy.orm import Session
from backend.app.models import Job, Chunk, KnowledgeSpace, JobStatus
from backend.app.services.vector_db_service_v2 import VectorDBServiceV2
from backend.app.services.ai_provider_service import AIProviderService
from backend.app.services.job.facade import JobService

logger = logging.getLogger(__name__)

BATCH_SIZE = 10  # Number of chunks to process in a single batch

@dramatiq.actor(
    queue_name="indexing",
    max_retries=3, 
    time_limit=3600_000
)
def indexing_actor(job_id: str):
    """
    A Dramatiq actor to perform vector indexing for all chunks of a document.
    """
    from backend.app.tasks.service_factory import get_services_scope
    job_uuid = uuid.UUID(job_id)
    logger.info(f"--- [Indexing Actor] Starting job ID: {job_uuid} ---")

    with get_services_scope() as services:
        db: Session = services["db"]
        job_service: JobService = services["job_service"]
        
        try:
            job = job_service.start_job(job_uuid)
            document = job.document
            if not document:
                raise ValueError(f"Document not found for job {job_id}")
            knowledge_space = document.knowledge_space
            if not knowledge_space:
                raise ValueError(f"KnowledgeSpace not found for document {document.id}")

            vector_db_service = VectorDBServiceV2()
            ai_provider_service: AIProviderService = services["ai_provider_service"]
            embedding_client = ai_provider_service.get_client_for_embedding(
                user_id=job.initiator_id,
                knowledge_space_id=job.knowledge_space_id
            )

            chunks_to_process = db.query(Chunk).filter(
                Chunk.document_id == document.id,
                Chunk.indexing_status != "indexed"
            ).all()
            
            total_chunks = len(chunks_to_process)
            if total_chunks == 0:
                job_service.finalize_job(job_uuid, status=JobStatus.COMPLETED, result={"message": "No chunks needed indexing."})
                db.commit()
                logger.info(f"--- [Indexing Actor] Job {job_uuid} COMPLETED (no chunks) ---")
                return

            embedding_dim = knowledge_space.ai_configuration.get("embedding", {}).get("dimension")
            model_name = getattr(embedding_client, 'model_name', knowledge_space.ai_configuration.get("embedding", {}).get('model_name'))
            
            logger.info(f"Job {job_uuid}: Starting indexing for {total_chunks} chunks. "
                        f"KS Config - Dimension: {embedding_dim}, Model: {model_name}")
            
            # Store actual dimension for collection management
            actual_embedding_dim = None

            # Flag to check if the model supports matryoshka. We assume it does initially.
            supports_matryoshka = True

            for i in range(0, total_chunks, BATCH_SIZE):
                batch = chunks_to_process[i:i + BATCH_SIZE]
                summary_texts = [chunk.summary or "" for chunk in batch]
                content_texts = [(chunk.paraphrase or chunk.raw_content) or "" for chunk in batch]
                
                embedding_params = {"model": model_name, "input": summary_texts}
                if supports_matryoshka and embedding_dim:
                    embedding_params["dimensions"] = embedding_dim

                try:
                    summary_response = embedding_client.embeddings.create(**embedding_params)
                    embedding_params["input"] = content_texts
                    content_response = embedding_client.embeddings.create(**embedding_params)
                except openai.BadRequestError as e:
                    if "does not support matryoshka representation" in str(e):
                        logger.info(f"Model '{model_name}' does not support dimension changes. Retrying without 'dimensions' parameter for this job.")
                        supports_matryoshka = False
                        embedding_params.pop("dimensions", None)
                        
                        # Retry without dimensions
                        summary_response = embedding_client.embeddings.create(**embedding_params)
                        embedding_params["input"] = content_texts
                        content_response = embedding_client.embeddings.create(**embedding_params)
                    else:
                        raise e

                summary_embeddings = [item.embedding for item in summary_response.data]
                content_embeddings = [item.embedding for item in content_response.data]

                # --- Dimension Detection and Collection Management ---
                if summary_embeddings:
                    actual_dim = len(summary_embeddings[0])
                    logger.info(f"Job {job_uuid}: Batch {i//BATCH_SIZE + 1}/{ (total_chunks + BATCH_SIZE - 1)//BATCH_SIZE}. "
                                f"Expected dim: {embedding_dim}, Actual dim from model: {actual_dim}")
                    
                    # Set actual dimension for first batch
                    if actual_embedding_dim is None:
                        actual_embedding_dim = actual_dim
                        logger.info(f"Job {job_uuid}: Using embedding dimension {actual_embedding_dim} for collection management")
                        
                        # Delete existing entries with the detected dimension
                        logger.info(f"Job {job_uuid}: Deleting existing index entries for document {document.id} with dimension {actual_embedding_dim}.")
                        vector_db_service.delete_by_document_id(
                            knowledge_space_id=str(knowledge_space.id),
                            document_id=str(document.id),
                            embedding_dim=actual_embedding_dim
                        )
                    
                    # Ensure consistency across batches
                    elif actual_dim != actual_embedding_dim:
                        raise ValueError(
                            f"Inconsistent embedding dimensions within job. "
                            f"First batch had dimension {actual_embedding_dim}, "
                            f"but current batch has dimension {actual_dim}."
                        )
                # --- End of Check ---

                insert_data = [{
                    "chunk_id": str(chunk.id), "document_id": str(document.id),
                    "summary_embedding": summary_embeddings[idx], "content_embedding": content_embeddings[idx]
                } for idx, chunk in enumerate(batch)]
                
                vector_db_service.insert(
                    knowledge_space_id=str(knowledge_space.id), 
                    data=insert_data,
                    embedding_dim=actual_embedding_dim
                )

                for chunk in batch:
                    chunk.indexing_status = "indexed"
                
                processed_count = i + len(batch)
                job_service.update_progress(job, "indexing", f"Processed {processed_count}/{total_chunks} chunks.")
                db.commit() # Commit progress intermittently

            job_service.finalize_job(job_uuid, status=JobStatus.COMPLETED, result={"indexed_chunks": total_chunks})
            db.commit()
            logger.info(f"--- [Indexing Actor] Job {job_uuid} COMPLETED successfully ---")

        except Exception as e:
            logger.error(f"--- [Indexing Actor] Job {job_uuid} FAILED: {e} ---", exc_info=True)
            job_service.finalize_job(job_uuid, status=JobStatus.FAILED, error_message=str(e))
            db.commit()
            raise
