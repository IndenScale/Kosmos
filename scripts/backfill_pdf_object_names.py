# /home/hxdi/Kosmos/scripts/backfill_pdf_object_names.py
import os
import sys
import logging
from io import BytesIO
from sqlalchemy.orm import joinedload

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Add project root to sys.path ---
# This allows importing modules from the 'backend' directory.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from backend.app.core.db import SessionLocal
    from backend.app.models.document import Document
    from backend.app.models.original import Original
    from backend.app.core.object_storage import get_minio_client
    from backend.app.utils.storage_utils import parse_storage_path
    from backend.app.core.config import settings
except ImportError as e:
    logging.error(f"Failed to import necessary modules. Make sure you are running this script from the project root "
                  f"or that the backend is correctly installed. Error: {e}")
    sys.exit(1)

def backfill_pdf_object_names():
    """
    Finds all documents that are PDFs and are missing the `pdf_object_name`,
    then creates a standardized copy in the `kosmos-pdfs` bucket and updates
    the database record.
    """
    logging.info("Connecting to the database and MinIO...")
    db = SessionLocal()
    minio = get_minio_client()
    
    try:
        # Eagerly load the 'original' relationship to avoid extra queries in the loop.
        documents_to_fix = db.query(Document).options(joinedload(Document.original)).join(
            Original, Document.original_id == Original.id
        ).filter(
            Original.detected_mime_type == 'application/pdf',
            Document.pdf_object_name.is_(None)
        ).all()

        if not documents_to_fix:
            logging.info("No PDF documents found that require backfilling.")
            return

        logging.info(f"Found {len(documents_to_fix)} PDF documents to fix.")

        for doc in documents_to_fix:
            logging.info(f"Processing document ID: {doc.id}...")

            try:
                # 1. Download the original file from object storage.
                original_storage_path = doc.original.storage_path
                if not original_storage_path:
                    logging.warning(f"  - Document {doc.id} has no original storage path. Skipping.")
                    continue
                
                bucket, object_name = parse_storage_path(original_storage_path)
                
                logging.info(f"  - Downloading original from bucket='{bucket}', object='{object_name}'...")
                pdf_content_response = minio.get_object(bucket, object_name)
                pdf_content = pdf_content_response.read()
                
                # It's good practice to close the connection.
                pdf_content_response.close()
                pdf_content_response.release_conn()

                # 2. Create a copy in the `kosmos-pdfs` bucket.
                new_pdf_object_name = f"{doc.id}.pdf"
                pdf_bucket = settings.MINIO_BUCKET_PDFS
                
                logging.info(f"  - Uploading copy to bucket='{pdf_bucket}', object='{new_pdf_object_name}'...")
                minio.put_object(
                    pdf_bucket,
                    new_pdf_object_name,
                    BytesIO(pdf_content),
                    len(pdf_content),
                    'application/pdf'
                )

                # 3. Update the `pdf_object_name` in the database.
                logging.info(f"  - Updating database record...")
                doc.pdf_object_name = new_pdf_object_name
                db.add(doc)
                db.commit()
                
                logging.info(f"  - Successfully fixed document {doc.id}.")

            except Exception as e:
                logging.error(f"  - Failed to process document {doc.id}: {e}", exc_info=True)
                db.rollback()

    finally:
        logging.info("Closing database connection.")
        db.close()

if __name__ == "__main__":
    logging.info("Starting backfill process for PDF object names...")
    backfill_pdf_object_names()
    logging.info("Backfill process finished.")
