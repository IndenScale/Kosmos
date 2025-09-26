# backend/app/tasks/content_extraction/pipelines.py
import os
import uuid
from io import BytesIO
from typing import Dict, Any
from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import Session
from minio import Minio

from ...models import Job, Document, CanonicalContent, Asset, DocumentAssetContext, ContentPageMapping
from ...models.asset import AssetType
from ...core.config import settings
from ...utils.file_utils import calculate_file_hash
from ...utils.storage_utils import generate_storage_path, parse_storage_path
from ...services.job.facade import JobService
from .libreoffice_client import convert_to_pdf, ConversionError
from .mineru_client import extract_content as run_mineru_extraction, MineruError
from .serializer import process_mineru_output
from .directory_manager import ContentExtractionDirectoryManager
from ...models.domain_events.ingestion_events import ToolExecutionRecord, FileInfo

# --- Helper Functions ---

def _create_or_get_canonical_content(db: Session, minio: Minio, content_bytes: bytes) -> CanonicalContent:
    content_hash = calculate_file_hash(content_bytes)
    cc = db.query(CanonicalContent).filter(CanonicalContent.content_hash == content_hash).first()
    if cc:
        return cc
    object_name = f"{content_hash}.md"
    storage_path = generate_storage_path(settings.MINIO_BUCKET_CANONICAL_CONTENTS, object_name)
    minio.put_object(settings.MINIO_BUCKET_CANONICAL_CONTENTS, object_name, BytesIO(content_bytes), len(content_bytes), "text/markdown")
    cc = CanonicalContent(content_hash=content_hash, size=len(content_bytes), storage_path=storage_path)
    db.add(cc)
    db.flush()
    return cc

# --- Pipeline Implementations ---

def run_office_pipeline(job: Job, job_service: JobService, override_storage_path: str = None) -> Dict[str, Any]:
    db = job_service.db
    minio = job_service.minio_client
    doc = job.document
    original = doc.original
    dir_manager = ContentExtractionDirectoryManager()

    storage_path = override_storage_path or original.storage_path
    
    bucket, object_name = parse_storage_path(storage_path)
    
    content_bytes = minio.get_object(bucket, object_name).read()
    
    # Get work directory for this file
    work_dir = dir_manager.get_work_directory(content_bytes, doc.original_filename)
    print(f"[Pipeline] Working directory: {work_dir}")

    job_service.update_progress(job, "conversion", "Converting Office document to PDF.")
    try:
        # CORRECTED: 'original_filename' is on the Document object ('doc'), not the Original object.
        pdf_content = convert_to_pdf(content_bytes, original_filename=doc.original_filename, dir_manager=dir_manager)
    except (FileNotFoundError, ConversionError) as e:
        raise Exception(f"LibreOffice conversion failed: {e}") from e

    pdf_object_name = f"{doc.id}.pdf"
    
    # Check if PDF is already in MinIO cache
    minio_dir = dir_manager.get_minio_directory(work_dir)
    cached_pdf_path = dir_manager.check_minio_cache(minio_dir, pdf_object_name)
    
    if not cached_pdf_path:
        minio.put_object(settings.MINIO_BUCKET_PDFS, pdf_object_name, BytesIO(pdf_content), len(pdf_content))
        # Save to cache
        dir_manager.save_minio_cache(minio_dir, pdf_object_name, pdf_content)
        print(f"[Pipeline] PDF uploaded to MinIO and cached")
    else:
        print(f"[Pipeline] Using cached PDF from MinIO: {cached_pdf_path}")
    
    doc.pdf_object_name = pdf_object_name
    db.add(doc)

    return run_pdf_pipeline(job, job_service, pdf_override_content=pdf_content)

def run_pdf_pipeline(job: Job, job_service: JobService, pdf_override_content: bytes = None) -> Dict[str, Any]:
    db = job_service.db
    minio = job_service.minio_client
    doc = job.document
    dir_manager = ContentExtractionDirectoryManager()
    
    pdf_content = pdf_override_content
    if not pdf_content:
        bucket, object_name = parse_storage_path(doc.original.storage_path)
        pdf_content = minio.get_object(bucket, object_name).read()

    # --- [BUG FIX] ---
    # Ensure the document has a pdf_object_name set at the beginning of the pipeline.
    # This guarantees that even for native PDFs, a standardized PDF copy is created
    # in the `kosmos-pdfs` bucket, which is required for page image rendering.
    if not doc.pdf_object_name:
        pdf_object_name = f"{doc.id}.pdf"
        # Save PDF to MinIO's PDF bucket
        minio.put_object(settings.MINIO_BUCKET_PDFS, pdf_object_name, BytesIO(pdf_content), len(pdf_content))
        doc.pdf_object_name = pdf_object_name
        db.add(doc)
        print(f"[Pipeline] PDF object name set for document {doc.id}: {pdf_object_name}")
    # --- [END BUG FIX] ---
    
    # Get work directory for this file - use content hash for stable paths
    pdf_hash = calculate_file_hash(pdf_content)
    pdf_filename = f"{pdf_hash}.pdf"
    work_dir = dir_manager.get_work_directory(pdf_content, pdf_filename)
    print(f"[Pipeline] Working directory: {work_dir}")
    print(f"[Pipeline] Using content-based filename: {pdf_filename}")

    job_service.update_progress(job, "extraction", "Extracting content with MinerU.")
    try:
        # Write PDF content to persistent directory for MinerU processing
        minio_dir = dir_manager.get_minio_directory(work_dir)
        pdf_file_path = os.path.join(minio_dir, pdf_filename)
        
        # Ensure directory exists
        os.makedirs(minio_dir, exist_ok=True)
        
        # Write PDF content to file if not cached
        if not os.path.exists(pdf_file_path):
            with open(pdf_file_path, 'wb') as f:
                f.write(pdf_content)
            print(f"[Pipeline] PDF written to: {pdf_file_path}")
        else:
            print(f"[Pipeline] Using existing PDF file: {pdf_file_path}")
        
        # Use directory manager for MinerU processing with caching
        mineru_result = run_mineru_extraction(pdf_file_path, pdf_filename, dir_manager=dir_manager)
        
        job_service.update_progress(job, "serialization", "Processing and serializing MinerU output.")
        serializer_result = process_mineru_output(mineru_result["output_path"], db, minio)

        # [DEBUG] Print the first 5 lines of the generated content before saving
        try:
            generated_content = serializer_result["canonical_content_bytes"].decode('utf-8')
            lines = generated_content.splitlines()
            print("--- [DEBUG] Generated Canonical Content (First 5 lines) ---")
            for i, line in enumerate(lines[:5]):
                print(f"  Line {i+1}: {line}")
            if not lines:
                print("  <EMPTY CONTENT>")
            print("---------------------------------------------------------")
        except Exception as e:
            print(f"--- [DEBUG] Error decoding or printing generated content: {e} ---")
        
    except (FileNotFoundError, MineruError) as e:
        raise Exception(f"MinerU extraction failed: {e}") from e

    canonical_content = _create_or_get_canonical_content(db, minio, serializer_result["canonical_content_bytes"])

    job_service.update_progress(job, "mapping", "Creating page mappings.")
    for mapping_info in serializer_result["page_mappings"]:
        mapping = ContentPageMapping(canonical_content_id=canonical_content.id, **mapping_info)
        db.add(mapping)

    # --- [BUG FIX V3] ---
    # Associate the processed assets with the current document using proper deduplication.
    # This handles both re-ingestion scenarios and multiple references to the same asset.
    job_service.update_progress(job, "asset_association", f"Associating {len(serializer_result['processed_assets'])} assets with document.")
    
    # Step 1: Collect all unique asset IDs from processed assets
    processed_asset_ids = set()
    for asset_obj in serializer_result["processed_assets"]:
        # Ensure the asset object is properly associated with the current session
        asset = db.merge(asset_obj)
        processed_asset_ids.add(asset.id)
    
    # Step 2: Query existing DocumentAssetContext records for this document and these assets
    existing_contexts = db.query(DocumentAssetContext).filter(
        DocumentAssetContext.document_id == doc.id,
        DocumentAssetContext.asset_id.in_(processed_asset_ids)
    ).all()
    
    existing_asset_ids = {context.asset_id for context in existing_contexts}
    print(f"[Pipeline] Found {len(existing_asset_ids)} existing DocumentAssetContext records")
    
    # Step 3: Determine which asset associations need to be created
    new_asset_ids = processed_asset_ids - existing_asset_ids
    print(f"[Pipeline] Need to create {len(new_asset_ids)} new DocumentAssetContext records")
    
    # Step 4: Batch create new DocumentAssetContext records
    if new_asset_ids:
        new_contexts = []
        for asset_id in new_asset_ids:
            context = DocumentAssetContext(document_id=doc.id, asset_id=asset_id)
            new_contexts.append(context)
            print(f"[Pipeline] Preparing new DocumentAssetContext for doc_id={doc.id}, asset_id={asset_id}")
        
        # Batch add all new contexts
        db.add_all(new_contexts)
        print(f"[Pipeline] Successfully prepared {len(new_contexts)} new DocumentAssetContext records for batch insertion")
    else:
        print(f"[Pipeline] No new DocumentAssetContext records needed - all assets already associated")
    # --- [END BUG FIX V3] ---

    # Import ToolExecutionRecord and create mineru_record
    from ...models.domain_events.ingestion_events import ToolExecutionRecord, FileInfo
    from datetime import datetime
    
    # Create ToolExecutionRecord for MinerU execution
    mineru_record = ToolExecutionRecord(
        command_executed=f"mineru -p {pdf_file_path} -o {mineru_result['output_path']}",
        start_time=datetime.now(),  # This should ideally come from mineru_result
        end_time=datetime.now(),    # This should ideally come from mineru_result
        input_files=[FileInfo(filename=pdf_filename, size_bytes=len(pdf_content))],
        exit_code=0,  # Assuming success since we got here
        result={
            "output_path": mineru_result["output_path"],
            "duration_seconds": mineru_result.get("duration_seconds", 0),
            "stdout": mineru_result.get("stdout", ""),
            "stderr": mineru_result.get("stderr", "")
        }
    )

    return {
        "canonical_content": canonical_content,
        "assets": serializer_result["processed_assets"],
        "mineru_record": mineru_record,
    }

def run_text_pipeline(job: Job, job_service: JobService) -> Dict[str, Any]:
    db = job_service.db
    minio = job_service.minio_client
    doc = job.document
    bucket, object_name = parse_storage_path(doc.original.storage_path)
    content_bytes = minio.get_object(bucket, object_name).read()
    
    canonical_content = _create_or_get_canonical_content(db, minio, content_bytes)
    
    line_count = len(content_bytes.decode('utf-8').splitlines())
    mapping = ContentPageMapping(canonical_content_id=canonical_content.id, line_from=1, line_to=line_count, page_number=1)
    db.add(mapping)
    
    # Create a default mineru_record for text pipeline
    now = datetime.now()
    mineru_record = ToolExecutionRecord(
        command_executed="text_pipeline",
        start_time=now,
        end_time=now,
        input_files=[FileInfo(filename=doc.original_filename, size_bytes=len(content_bytes))],
        exit_code=0,
        result={"pipeline_type": "text"}
    )
    
    return {"canonical_content": canonical_content, "assets": [], "mineru_record": mineru_record}

def run_image_pipeline(job: Job, job_service: JobService) -> Dict[str, Any]:
    db = job_service.db
    minio = job_service.minio_client
    doc = job.document
    bucket, object_name = parse_storage_path(doc.original.storage_path)
    content_bytes = minio.get_object(bucket, object_name).read()
    
    # Asset creation logic needs to be self-contained or imported
    from ...utils.file_utils import calculate_file_hash
    asset_hash = calculate_file_hash(content_bytes)
    asset = db.query(Asset).filter(Asset.asset_hash == asset_hash).first()
    if not asset:
        file_type = doc.original_filename.split('.')[-1] if '.' in doc.original_filename else 'png'
        object_name = f"{asset_hash}.{file_type}"
        storage_path = generate_storage_path(settings.MINIO_BUCKET_ASSETS, object_name)
        minio.put_object(settings.MINIO_BUCKET_ASSETS, object_name, BytesIO(content_bytes), len(content_bytes), f"image/{file_type}")
        asset = Asset(asset_hash=asset_hash, asset_type=AssetType.figure, file_type=file_type, size=len(content_bytes), storage_path=storage_path, reference_count=1)
        db.add(asset)
    else:
        asset.reference_count += 1
        db.add(asset)
    
    # Flush to ensure asset.id is available before creating context
    db.flush()
    
    context = DocumentAssetContext(document_id=doc.id, asset_id=asset.id)
    db.add(context)
    
    empty_cc = _create_or_get_canonical_content(db, minio, b"")
    
    # Create a default mineru_record for image pipeline
    now = datetime.now()
    mineru_record = ToolExecutionRecord(
        command_executed="image_pipeline",
        start_time=now,
        end_time=now,
        input_files=[FileInfo(filename=doc.original_filename, size_bytes=len(content_bytes))],
        exit_code=0,
        result={"pipeline_type": "image"}
    )
    
    return {"canonical_content": empty_cc, "assets": [asset], "mineru_record": mineru_record}
