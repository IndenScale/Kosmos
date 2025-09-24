import uuid
import io
import zipfile
import mimetypes
import json
from typing import Optional, List, Dict, Any
from fastapi import UploadFile, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, func
from minio import Minio

from ...models import User, Document, KnowledgeSpace
from ...models.domain_events import DomainEvent
from ...models.domain_events.ingestion_events import (
    DocumentRegisteredPayload,
    ContentExtractionStrategy,
    AssetAnalysisStrategy,
)
from ...services import document_service
from ...services import JobService
from .utils import is_supported_file_type, get_normalized_mime_type, process_embedded_file


class IngestionService:
    """
    A service class dedicated to handling the document ingestion process.
    It orchestrates the registration of documents and the publication of
    domain events to trigger subsequent processing.
    """
    def __init__(self, db: Session, minio: Minio, job_service: JobService):
        self.db = db
        self.minio = minio
        self.job_service = job_service

    def _publish_document_registered_event(
        self,
        document: Document,
        uploader: User,
        force: bool,
        content_extraction_strategy: Optional[ContentExtractionStrategy],
        asset_analysis_strategy: Optional[AssetAnalysisStrategy],
        chunking_strategy_name: Optional[str],
    ):
        """
        Creates and stages a DocumentRegistered domain event within the current
        database transaction.
        """
        if not document.original:
            # This should not happen if the document is correctly created
            raise ValueError(f"Document {document.id} is missing its Original record.")

        payload = DocumentRegisteredPayload(
            document_id=document.id,
            knowledge_space_id=document.knowledge_space_id,
            original_id=document.original_id,
            initiator_id=uploader.id,
            original_filename=document.original_filename,
            reported_mime_type=document.original.reported_file_type,
            file_size_bytes=document.original.size,
            force=force,
            content_extraction_strategy=content_extraction_strategy,
            asset_analysis_strategy=asset_analysis_strategy,
            chunking_strategy_name=chunking_strategy_name,
        )

        # Ensure payload is JSON serializable before creating the DomainEvent
        try:
            # Pydantic V2+
            payload_json_str = payload.model_dump_json(exclude_none=True)
        except AttributeError:
            # Fallback for Pydantic V1
            payload_json_str = payload.json(exclude_none=True)

        # 存储为JSON字符串，以确保Unicode字符正确处理
        domain_event = DomainEvent(
            aggregate_id=str(document.id),
            event_type="DocumentRegisteredPayload",
            payload=payload_json_str,
        )
        self.db.add(domain_event)
        # [DEBUG] Log the initiator_id being used for the event
        print(f"  - [INGESTION-DEBUG] Staging 'DocumentRegistered' event for doc {document.id} with initiator_id: {uploader.id}")

    async def ingest_document(
        self,
        knowledge_space_id: uuid.UUID,
        file: UploadFile,
        uploader: User,
        force: bool = False,
        content_extraction_strategy: Optional[ContentExtractionStrategy] = None,
        asset_analysis_strategy: Optional[AssetAnalysisStrategy] = None,
        chunking_strategy_name: Optional[str] = None,
    ) -> Document:
        """
        Orchestrates the registration of an uploaded document, handling potential
        container files (like ZIPs) and publishing DocumentRegistered events for
        each registered document (parent and children).
        """
        file_contents = await file.read()

        # Use a transaction to ensure all or nothing
        try:
            # --- Register Parent Document ---
            parent_original = document_service.create_or_get_original(
                db=self.db,
                contents=file_contents,
                filename=file.filename,
                reported_mime_type=file.content_type or "application/octet-stream"
            )
            parent_document = document_service.create_document_record(
                db=self.db,
                knowledge_space_id=knowledge_space_id,
                original_id=parent_original.id,
                original_filename=file.filename,
                uploader_id=uploader.id
            )

            # The parent document itself might be processable (e.g., a Word doc with macros)
            # So we always publish an event for it.
            self._publish_document_registered_event(
                document=parent_document,
                uploader=uploader,
                force=force,
                content_extraction_strategy=content_extraction_strategy,
                asset_analysis_strategy=asset_analysis_strategy,
                chunking_strategy_name=chunking_strategy_name,
            )

            # --- Handle Container Files (ZIP) ---
            if zipfile.is_zipfile(io.BytesIO(file_contents)):
                print(f"'{file.filename}' is a container file. Extracting and registering children.")
                
                # [FIX] Track processed original IDs within this single upload to prevent
                # creating duplicate Document records for identical embedded files.
                processed_original_ids = set()

                with zipfile.ZipFile(io.BytesIO(file_contents)) as zf:
                    for sub_filename in zf.namelist():
                        # Skip directories and macOS resource forks
                        if sub_filename.endswith('/') or sub_filename.startswith('__MACOSX/'):
                            continue

                        with zf.open(sub_filename) as sub_file:
                            sub_file_contents = sub_file.read()
                            if not sub_file_contents:
                                print(f"  - Skipping empty file: {sub_filename}")
                                continue

                            # 使用白名单检查文件类型
                            sub_mime_type = mimetypes.guess_type(sub_filename)[0] or "application/octet-stream"
                            
                            # 处理嵌入文件：重命名和二进制裁剪
                            processed_filename, processed_content, normalized_mime_type, was_renamed, was_trimmed = process_embedded_file(
                                sub_filename, sub_file_contents, sub_mime_type
                            )
                            
                            if not is_supported_file_type(processed_filename, processed_content, normalized_mime_type):
                                print(f"  - Skipping unsupported file type: {processed_filename} (original: {sub_filename})")
                                continue

                            sub_original = document_service.create_or_get_original(
                                db=self.db,
                                contents=processed_content,  # 使用处理后的内容
                                filename=processed_filename,  # 使用处理后的文件名
                                reported_mime_type=normalized_mime_type
                            )

                            # [FIX] Check for duplicates before creating the document record
                            if sub_original.id in processed_original_ids:
                                print(f"  - Skipping duplicate embedded content: {processed_filename} (original: {sub_filename})")
                                continue
                            
                            processed_original_ids.add(sub_original.id)

                            processing_info = []
                            if was_renamed:
                                processing_info.append(f"renamed from {sub_filename}")
                            if was_trimmed:
                                processing_info.append("binary wrapper trimmed")
                            
                            processing_desc = f" ({', '.join(processing_info)})" if processing_info else ""
                            print(f"  - Registering child document: {processed_filename}{processing_desc}")

                            sub_document = document_service.create_document_record(
                                db=self.db,
                                knowledge_space_id=knowledge_space_id,
                                original_id=sub_original.id,
                                original_filename=processed_filename,  # 使用处理后的文件名
                                uploader_id=uploader.id,
                                parent_document_id=parent_document.id
                            )
                            self._publish_document_registered_event(
                                document=sub_document,
                                uploader=uploader,
                                force=force,
                                content_extraction_strategy=content_extraction_strategy,
                                asset_analysis_strategy=asset_analysis_strategy,
                                chunking_strategy_name=chunking_strategy_name,
                            )

            self.db.commit()
            return parent_document

        except Exception as e:
            print(f"Error during ingestion, rolling back transaction. Error: {e}")
            self.db.rollback()
            # Re-raise as a standard exception that the router can handle
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to ingest document: {e}"
            )

    def reingest_documents(
        self,
        uploader: User,
        document_ids: Optional[List[uuid.UUID]] = None,
        knowledge_space_id: Optional[uuid.UUID] = None,
        force: bool = True,
        content_extraction_strategy: Optional[ContentExtractionStrategy] = None,
        asset_analysis_strategy: Optional[AssetAnalysisStrategy] = None,
        chunking_strategy_name: Optional[str] = None,
    ) -> int:
        """
        Re-ingests existing documents by publishing DocumentRegistered events.
        This operation is permission-aware and will only re-ingest documents
        that the uploader has access to (either as an owner or a member).

        Args:
            uploader: The user initiating the re-ingestion.
            document_ids: Specific document IDs to re-ingest (optional).
            knowledge_space_id: Re-ingest all documents in this knowledge space (optional).
            force: Whether to force re-processing.
            content_extraction_strategy: Strategy for content extraction.
            asset_analysis_strategy: Strategy for asset analysis.
            chunking_strategy_name: Name of the chunking strategy.

        Returns:
            Number of documents successfully scheduled for re-ingestion.
        """
        from ...models import KnowledgeSpace, KnowledgeSpaceMember
        from sqlalchemy import or_
        try:
            # --- CORRECTED AUTHORIZATION-AWARE QUERY ---
            # A user has access if they are the OWNER of the knowledge space
            # OR a MEMBER of it. Using direct UUID comparison.
            
            query = self.db.query(Document).join(
                KnowledgeSpace, Document.knowledge_space_id == KnowledgeSpace.id
            ).outerjoin(
                KnowledgeSpaceMember, Document.knowledge_space_id == KnowledgeSpaceMember.knowledge_space_id
            ).filter(
                or_(
                    KnowledgeSpace.owner_id == uploader.id,
                    KnowledgeSpaceMember.user_id == uploader.id
                )
            ).options(
                joinedload(Document.original)
            )

            # Apply the specific filters on top of the authorized documents.
            if document_ids:
                # Apply direct UUID comparison for the IN clause
                query = query.filter(Document.id.in_(document_ids))
            elif knowledge_space_id:
                query = query.filter(Document.knowledge_space_id == knowledge_space_id)
            else:
                # This case should be prevented by the router's validation, but as a safeguard:
                raise ValueError("Either document_ids or knowledge_space_id must be provided")

            documents = query.all()

            if not documents:
                print("No documents found matching the criteria for the current user.")
                return 0

            print(f"Found {len(documents)} documents to re-ingest for user {uploader.id}...")

            # Publish events for each document
            for document in documents:
                print(f"  - Scheduling re-ingestion for: {document.original_filename} (ID: {document.id})")
                self._publish_document_registered_event(
                    document=document,
                    uploader=uploader,
                    force=force,
                    content_extraction_strategy=content_extraction_strategy,
                    asset_analysis_strategy=asset_analysis_strategy,
                    chunking_strategy_name=chunking_strategy_name,
                )

            self.db.commit()
            print(f"Successfully scheduled {len(documents)} documents for re-ingestion.")
            return len(documents)

        except Exception as e:
            print(f"Error during re-ingestion, rolling back transaction. Error: {e}")
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to re-ingest documents: {e}"
            )
