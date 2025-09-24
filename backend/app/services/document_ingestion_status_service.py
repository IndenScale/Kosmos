"""
Service layer for checking document ingestion status in a knowledge space.
"""
import os
from uuid import UUID
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from sqlalchemy import and_

from .. import models
from ..schemas.document import DocumentIngestionStatusResponse, DocumentIngestionStatusDetail

def check_document_ingestion_status(
    db: Session, 
    knowledge_space_id: UUID
) -> DocumentIngestionStatusResponse:
    """
    Check the ingestion status of all documents in a knowledge space.
    
    This function:
    1. Gets all valid documents (excluding unsupported file types)
    2. Checks for canonical content
    3. Calculates asset analysis completion rate (both document-level and KS-level)
    4. Identifies pending jobs that might be blocking analysis
    
    Returns:
        DocumentIngestionStatusResponse: Status information for all documents
    """
    # Get all documents in the knowledge space
    documents = db.query(models.Document).filter(
        models.Document.knowledge_space_id == knowledge_space_id
    ).all()
    
    # Filter out unsupported file types
    supported_extensions = {'.pdf', '.docx', '.txt', '.md', '.html', '.xml', '.csv'}
    valid_documents = [
        doc for doc in documents 
        if os.path.splitext(doc.original_filename)[1].lower() in supported_extensions
    ]
    
    # Check each document
    document_details = []
    total_documents = len(valid_documents)
    documents_with_canonical_content = 0
    documents_with_asset_analysis = 0
    documents_with_pending_jobs = 0
    # Counters for the new overall asset analysis rate
    total_assets_in_ks = 0
    total_completed_assets_in_ks = 0
    
    for doc in valid_documents:
        try:
            detail = _check_single_document(db, doc)
            document_details.append(detail)
            
            # Update counters
            if detail.has_canonical_content:
                documents_with_canonical_content += 1
            if detail.asset_analysis_completion_rate == 1.0:
                documents_with_asset_analysis += 1
            if detail.has_pending_jobs:
                documents_with_pending_jobs += 1
            
            # Aggregate asset counts for the new overall metric
            total_assets_in_ks += detail.total_assets
            total_completed_assets_in_ks += detail.completed_assets

        except Exception as e:
            # Log error but continue processing other documents
            print(f"Error processing document {doc.id}: {str(e)}")
            # Add a minimal detail for this document
            document_details.append(
                DocumentIngestionStatusDetail(
                    document_id=doc.id,
                    document_name=doc.original_filename,
                    has_canonical_content=False,
                    total_assets=0,
                    completed_assets=0,
                    asset_analysis_completion_rate=0.0,
                    has_pending_jobs=False,
                    suggestions=[f"Error processing document: {str(e)}"]
                )
            )
    
    # Calculate overall statistics
    canonical_content_rate = documents_with_canonical_content / total_documents if total_documents > 0 else 0
    asset_analysis_rate = documents_with_asset_analysis / total_documents if total_documents > 0 else 0
    pending_jobs_rate = documents_with_pending_jobs / total_documents if total_documents > 0 else 0
    # Calculate the new, more practical overall asset analysis rate
    overall_asset_analysis_rate = total_completed_assets_in_ks / total_assets_in_ks if total_assets_in_ks > 0 else 1.0
    
    return DocumentIngestionStatusResponse(
        knowledge_space_id=knowledge_space_id,
        total_documents=total_documents,
        documents_with_canonical_content=documents_with_canonical_content,
        documents_with_asset_analysis=documents_with_asset_analysis,
        documents_with_pending_jobs=documents_with_pending_jobs,
        canonical_content_rate=canonical_content_rate,
        asset_analysis_rate=asset_analysis_rate,
        pending_jobs_rate=pending_jobs_rate,
        total_assets_in_ks=total_assets_in_ks,
        total_completed_assets_in_ks=total_completed_assets_in_ks,
        overall_asset_analysis_rate=overall_asset_analysis_rate,
        documents=document_details
    )

def _check_single_document(db: Session, document: models.Document) -> DocumentIngestionStatusDetail:
    """
    Check the ingestion status of a single document.
    
    Args:
        db: Database session
        document: Document model instance
        
    Returns:
        DocumentIngestionStatusDetail: Detailed status for the document
    """
    # Check for canonical content
    has_canonical_content = document.canonical_content is not None
    
    # Get asset contexts for this document
    asset_contexts = document.asset_contexts
    
    # Calculate asset analysis completion rate
    total_assets = len(asset_contexts)
    completed_assets = 0
    pending_jobs = 0
    
    for context in asset_contexts:
        # Check if asset has analysis result
        if context.analysis_result is not None and context.analysis_result.strip():
            completed_assets += 1
        # Check if there's a pending job
        elif context.job and context.job.status == 'PENDING':
            pending_jobs += 1
    
    # Calculate completion rate
    completion_rate = completed_assets / total_assets if total_assets > 0 else 1.0
    
    # Check for pending jobs
    has_pending_jobs = pending_jobs > 0
    
    # Generate suggestions based on status
    suggestions = []
    if not has_canonical_content:
        suggestions.append("Document lacks canonical content. This may prevent full text analysis.")
    if completion_rate < 1.0 and not has_pending_jobs:
        suggestions.append("Some assets lack analysis results. Consider reprocessing the document.")
    elif has_pending_jobs:
        suggestions.append("Some asset analysis jobs are pending. Please wait for completion.")
    
    return DocumentIngestionStatusDetail(
        document_id=document.id,
        document_name=document.original_filename,
        has_canonical_content=has_canonical_content,
        total_assets=total_assets,
        completed_assets=completed_assets,
        asset_analysis_completion_rate=completion_rate,
        has_pending_jobs=has_pending_jobs,
        suggestions=suggestions
    )