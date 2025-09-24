import uuid
from sqlalchemy.orm import Session
from backend.app.models import Job, Document
from backend.app.models.job import JobType, JobStatus
from backend.app.models.credential import CredentialType

def _find_conflicting_job(db: Session, document_id: uuid.UUID, job_type: JobType) -> Job | None:
    """Finds a running or pending job of the same type for the same document."""
    return db.query(Job).filter(
        Job.document_id == document_id,
        Job.job_type == job_type,
        Job.status.in_([JobStatus.RUNNING, JobStatus.PENDING])
    ).first()

def create_document_processing_job(db: Session, document_id: uuid.UUID, initiator_id: uuid.UUID, force: bool = False) -> Job:
    """
    Creates a new document processing job.
    If force=true, it will abort any existing running/pending job of the same type.
    If force=false, it will return the existing running/pending job if found.
    """
    from sqlalchemy import update
    conflicting_job = _find_conflicting_job(db, document_id, JobType.DOCUMENT_PROCESSING)

    if conflicting_job:
        if force:
            # [ROBUSTNESS FIX] Use an explicit update statement
            # to ensure the WHERE clause works correctly with SQLite UUIDs.
            db.execute(
                update(Job)
                .where(Job.id == conflicting_job.id)
                .values(
                    status=JobStatus.ABORTED,
                    error_message=f"Job aborted by user {initiator_id} due to forced reprocessing."
                )
            )
        else:
            # If not forcing, just return the existing job without creating a new one
            return conflicting_job

    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise ValueError(f"Document with id {document_id} not found.")
    
    job = Job(
        document_id=document_id,
        knowledge_space_id=doc.knowledge_space_id,
        initiator_id=initiator_id,
        job_type=JobType.DOCUMENT_PROCESSING,
        status=JobStatus.PENDING,
        credential_type_preference=CredentialType.NONE # This job doesn't directly use credentials
    )
    db.add(job)
    db.flush()
    # The commit is handled by the calling service layer
    return job

def create_content_extraction_job(db: Session, document_id: uuid.UUID, initiator_id: uuid.UUID, force: bool = False, context: dict = None) -> Job:
    """
    Creates a new content extraction job.
    If force=true, it will abort any existing running/pending job of the same type.
    If force=false, it will return the existing running/pending job if found.
    """
    from sqlalchemy import update
    conflicting_job = _find_conflicting_job(db, document_id, JobType.CONTENT_EXTRACTION)

    if conflicting_job:
        if force:
            # [ROBUSTNESS FIX] Use an explicit update statement
            # to ensure the WHERE clause works correctly with SQLite UUIDs.
            db.execute(
                update(Job)
                .where(Job.id == conflicting_job.id)
                .values(
                    status=JobStatus.ABORTED,
                    error_message=f"Job aborted by user {initiator_id} due to forced reprocessing."
                )
            )
        else:
            # If not forcing, just return the existing job without creating a new one
            return conflicting_job

    # Find the document and its knowledge space ID in a robust way
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        # This should ideally not happen if the event is valid
        raise ValueError(f"Document with id {document_id} not found during job creation.")

    job = Job(
        document_id=document_id,
        knowledge_space_id=doc.knowledge_space_id,
        initiator_id=initiator_id,
        job_type=JobType.CONTENT_EXTRACTION,
        status=JobStatus.PENDING,
        credential_type_preference=CredentialType.NONE, # This job doesn't directly use credentials
        context=context or {}
    )
    db.add(job)
    db.flush()
    # The commit is handled by the calling service layer
    return job

def create_chunking_job(db: Session, document_id: uuid.UUID, initiator_id: uuid.UUID, credential_type_preference: CredentialType, context: dict = None, force: bool = False) -> Job:
    """Creates a new chunking job."""
    if not force and _find_conflicting_job(db, document_id, JobType.CHUNKING):
        raise ValueError("A chunking job for this document is already running or pending.")
    
    # Ensure a default credential type preference if none is provided.
    final_credential_preference = credential_type_preference or CredentialType.SLM

    # If no context is provided, use the default. Otherwise, use the provided context.
    final_context = context if context is not None else {"chunking_params": {"splitter": "rule_based"}}

    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise ValueError(f"Document with id {document_id} not found.")
    
    job = Job(
        document_id=document_id,
        knowledge_space_id=doc.knowledge_space_id,
        initiator_id=initiator_id,
        job_type=JobType.CHUNKING,
        status=JobStatus.PENDING,
        credential_type_preference=final_credential_preference,
        context=final_context
    )
    db.add(job)
    db.flush()
    return job

def create_indexing_job(db: Session, document_id: uuid.UUID, initiator_id: uuid.UUID, force: bool = False) -> Job:
    """Creates a new indexing job."""
    if not force and _find_conflicting_job(db, document_id, JobType.INDEXING):
        raise ValueError("An indexing job for this document is already running or pending.")

    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise ValueError(f"Document with id {document_id} not found.")
    
    job = Job(
        document_id=document_id,
        knowledge_space_id=doc.knowledge_space_id,
        initiator_id=initiator_id,
        job_type=JobType.INDEXING,
        status=JobStatus.PENDING,
        credential_type_preference=CredentialType.EMBEDDING
    )
    db.add(job)
    db.flush()
    return job

def create_tagging_job(db: Session, document_id: uuid.UUID, initiator_id: uuid.UUID, mode: str, force: bool = False) -> Job:
    """Creates a new tagging job."""
    if not force and _find_conflicting_job(db, document_id, JobType.TAGGING):
        raise ValueError("A tagging job for this document is already running or pending.")

    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise ValueError(f"Document with id {document_id} not found.")
    
    job = Job(
        document_id=document_id,
        knowledge_space_id=doc.knowledge_space_id,
        initiator_id=initiator_id,
        job_type=JobType.TAGGING,
        status=JobStatus.PENDING,
        context={"mode": mode},
        credential_type_preference=CredentialType.LLM
    )
    db.add(job)
    db.flush()
    return job

def create_asset_analysis_job(db: Session, document_id: uuid.UUID, asset_id: uuid.UUID, initiator_id: uuid.UUID) -> Job:
    """Creates a new asset analysis job."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise ValueError(f"Document with id {document_id} not found.")
    
    job = Job(
        document_id=document_id,
        knowledge_space_id=doc.knowledge_space_id,
        initiator_id=initiator_id,
        job_type=JobType.ASSET_ANALYSIS,
        status=JobStatus.PENDING,
        context={"asset_id": str(asset_id)},
        credential_type_preference=CredentialType.VLM
    )
    db.add(job)
    db.flush()
    return job

def create_knowledge_space_batch_job(
    db: Session,
    knowledge_space_id: uuid.UUID,
    initiator_id: uuid.UUID,
    tasks: list[str]
) -> Job:
    """
    Creates a new batch processing job for a knowledge space.
    """
    job = Job(
        knowledge_space_id=knowledge_space_id,
        initiator_id=initiator_id,
        job_type=JobType.KNOWLEDGE_SPACE_BATCH_PROCESS,
        status=JobStatus.PENDING,
        context={"tasks": tasks},
        # This job type doesn't require a specific credential preference up-front
        credential_type_preference=CredentialType.NONE 
    )
    db.add(job)
    db.flush()
    # Commit is handled by the service layer
    return job