import uuid
import os
import json
import redis
from typing import List, Dict, Any, Optional
from datetime import timedelta
from fastapi import HTTPException, status
from minio import Minio
from sqlalchemy import func, case
from sqlalchemy.orm import Session

from .. import schemas
from ..models import Asset, Document, DocumentAssetContext, KnowledgeSpace, User
import tempfile
import base64
from ..models.asset import AssetAnalysisStatus
from ..services.ai_provider_service import AIProviderService
from ..core.config import settings
from ..models import KnowledgeSpaceMember
from ..utils.storage_utils import parse_storage_path

import zipstream
from io import BytesIO

class AssetService:
    """Handles all business logic related to assets."""

    def __init__(self, db: Session, minio: Minio, redis_cache: redis.Redis, ai_provider_service: AIProviderService):
        self.db = db
        self.minio = minio
        self.redis_cache = redis_cache
        self.ai_provider_service = ai_provider_service

    def get_assets(
        self,
        user_id: uuid.UUID,
        knowledge_space_id: Optional[uuid.UUID] = None,
        document_id: Optional[uuid.UUID] = None,
        asset_type: Optional[str] = None,
        analysis_status: Optional[str] = None,
        file_types: Optional[List[str]] = None,
        limit: int = 20,
        cursor: Optional[str] = None,
    ) -> (List[Dict[str, Any]], int):
        """
        [REWRITTEN] Gets a paginated and filtered list of assets based on user permissions.
        This version correctly derives the analysis_status from the DocumentAssetContext.
        """
        # Define the dynamic analysis_status using a CASE statement.
        # This is the core of the fix.
        analysis_status_case = case(
            (DocumentAssetContext.analysis_result != None, AssetAnalysisStatus.COMPLETED.value),
            else_=AssetAnalysisStatus.NOT_ANALYZED.value
        ).label("analysis_status")

        # The base query now selects from DocumentAssetContext and includes the dynamic status.
        query = self.db.query(
            DocumentAssetContext,
            Asset,
            Document,
            analysis_status_case
        )

        # Join Asset and Document tables.
        query = query.join(Asset, DocumentAssetContext.asset_id == Asset.id)\
                     .join(Document, DocumentAssetContext.document_id == Document.id)

        # Apply filters based on user permissions and request parameters.
        if document_id:
            query = query.filter(Document.id == document_id)
        elif knowledge_space_id:
            # Filter by the specified knowledge space, ensuring user has access.
            user_ks_ids_query = self.db.query(KnowledgeSpaceMember.knowledge_space_id).filter(
                KnowledgeSpaceMember.user_id == user_id,
                KnowledgeSpaceMember.knowledge_space_id == knowledge_space_id
            )
            query = query.filter(Document.knowledge_space_id.in_(user_ks_ids_query))
        else:
            # Filter by all knowledge spaces the user is a member of.
            user_ks_ids_query = self.db.query(KnowledgeSpaceMember.knowledge_space_id).filter(
                KnowledgeSpaceMember.user_id == user_id
            )
            query = query.filter(Document.knowledge_space_id.in_(user_ks_ids_query))

        # Apply additional filters.
        if asset_type:
            query = query.filter(Asset.asset_type == asset_type)
        if file_types:
            query = query.filter(Asset.file_type.in_(file_types))
        
        # Apply the filter on the dynamically calculated status.
        if analysis_status:
            query = query.filter(analysis_status_case == analysis_status)

        # Get total count before pagination.
        # The count should be on the composite primary key of the context table.
        total_count_query = query.with_entities(func.count(DocumentAssetContext.asset_id))
        total_count = total_count_query.scalar()

        # Handle cursor-based pagination.
        if cursor:
            # Assuming cursor is a timestamp from created_at of the context.
            query = query.filter(DocumentAssetContext.created_at > cursor)

        # Order and limit the results.
        results = query.order_by(DocumentAssetContext.created_at).limit(limit).all()
        
        # Manually construct a list of dictionaries that match the AssetRead schema.
        assets_data = []
        for context, asset, document, calculated_status in results:
            assets_data.append({
                "id": asset.id,
                "asset_type": asset.asset_type,
                "file_type": asset.file_type,
                "analysis_status": calculated_status, # Use the calculated status.
                "knowledge_space_id": document.knowledge_space_id,
                "document_id": document.id,
                "storage_path": asset.storage_path,
                "created_at": context.created_at, # Use context's created_at for consistency.
                "updated_at": context.updated_at,
            })
        
        return assets_data, total_count


    def get_assets_by_ids(self, asset_ids: List[uuid.UUID], knowledge_space_id: uuid.UUID) -> List[Dict[str, Any]]:
        """
        Gets a list of assets by their IDs, including their latest analysis result,
        ensuring they are linked to the specified knowledge space.
        """
        # Verify that all assets are linked to the specified knowledge space
        valid_assets_query = (self.db.query(Asset.id)
            .join(DocumentAssetContext, Asset.id == DocumentAssetContext.asset_id)
            .join(Document, DocumentAssetContext.document_id == Document.id)
            .filter(Document.knowledge_space_id == knowledge_space_id)
            .filter(Asset.id.in_(asset_ids))
            .distinct())
        
        valid_asset_ids = {row[0] for row in valid_assets_query}
        
        requested_ids = set(asset_ids)
        if not requested_ids.issubset(valid_asset_ids):
            missing_ids = requested_ids - valid_asset_ids
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Assets not found or not in the specified knowledge space: {', '.join(map(str, missing_ids))}"
            )

        # Fetch assets and their most recent analysis context
        assets_with_context = (self.db.query(Asset, DocumentAssetContext)
            .outerjoin(DocumentAssetContext, Asset.id == DocumentAssetContext.asset_id)
            .filter(Asset.id.in_(asset_ids))
            .order_by(Asset.id, DocumentAssetContext.updated_at.desc())
            .distinct(Asset.id)
            .all())

        results = []
        for asset, context in assets_with_context:
            # Manually construct the dictionary to avoid ORM mapping issues
            asset_data = {
                "id": asset.id,
                "asset_type": asset.asset_type,
                "file_type": asset.file_type,
                "analysis_status": asset.analysis_status,
                "knowledge_space_id": knowledge_space_id,
                "document_id": context.document_id if context else None,
                "storage_path": asset.storage_path,
                "created_at": asset.created_at,
                "updated_at": context.updated_at if context else asset.created_at,
                "analysis_result": None,
                "model_version": None
            }

            if context and asset.analysis_status == AssetAnalysisStatus.COMPLETED:
                asset_data['analysis_result'] = context.analysis_result
                asset_data['model_version'] = f"{context.model_provider}/{context.model_name}" if context.model_name else None
            
            results.append(asset_data)
            
        return results

    def create_download_archive(self, asset_ids: List[uuid.UUID], knowledge_space_id: uuid.UUID):
        """
        Creates a zip archive of assets for streaming download.
        """
        # Similar validation as get_assets_by_ids
        assets = (self.db.query(Asset)
            .join(DocumentAssetContext, Asset.id == DocumentAssetContext.asset_id)
            .join(Document, DocumentAssetContext.document_id == Document.id)
            .filter(Document.knowledge_space_id == knowledge_space_id)
            .filter(Asset.id.in_(asset_ids))
            .distinct().all())

        if len(assets) != len(set(asset_ids)):
            raise HTTPException(status_code=404, detail="Some assets were not found or do not belong to the specified knowledge space.")

        def file_generator():
            z = zipstream.ZipFile(mode='w', compression=zipstream.ZIP_DEFLATED)
            for asset in assets:
                try:
                    bucket_name, object_name = parse_storage_path(asset.storage_path)
                    file_data = self.minio.get_object(bucket_name, object_name)
                    # Use a unique filename for the archive
                    archive_filename = f"{asset.id}{os.path.splitext(object_name)[1]}"
                    z.write_iter(archive_filename, file_data.stream(32*1024))
                except Exception:
                    # Log the error but continue zipping other files
                    print(f"Error streaming asset {asset.id} from Minio. Skipping.")
                    continue
            
            for chunk in z:
                yield chunk

        return file_generator()

    def delete_assets_by_ids(self, asset_ids: List[uuid.UUID], knowledge_space_id: uuid.UUID) -> int:
        """
        Deletes assets by their IDs, ensuring they belong to the specified knowledge space.
        This is a soft delete for the records; it does not yet remove files from Minio.
        """
        # First, verify all assets belong to the knowledge space to prevent unauthorized deletion
        assets_to_delete_q = self.db.query(Asset).join(
            DocumentAssetContext, Asset.id == DocumentAssetContext.asset_id
        ).join(
            Document, DocumentAssetContext.document_id == Document.id
        ).filter(
            Document.knowledge_space_id == knowledge_space_id,
            Asset.id.in_(asset_ids)
        )
        
        assets_to_delete = assets_to_delete_q.all()

        if len(assets_to_delete) != len(set(asset_ids)):
            # Find which IDs were not found or didn't match the knowledge space
            found_ids = {asset.id for asset in assets_to_delete}
            missing_ids = [str(aid) for aid in asset_ids if aid not in found_ids]
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Some assets were not found or do not belong to the specified knowledge space: {', '.join(missing_ids)}"
            )
        
        # Delete associated context links first
        self.db.query(DocumentAssetContext).filter(
            DocumentAssetContext.asset_id.in_(asset_ids)
        ).delete(synchronize_session=False)

        # Now delete the assets
        deleted_count = self.db.query(Asset).filter(
            Asset.id.in_(asset_ids)
        ).delete(synchronize_session=False)
        
        self.db.commit()
        return deleted_count

    def _get_asset_base64(self, asset: Asset) -> str:
        """Downloads an asset from Minio and returns its base64 encoded content."""
        tmp_file_path = None
        try:
            # Create a temporary file and get its path
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                tmp_file_path = tmp_file.name
            
            # Download the object to the temporary file path
            bucket_name, object_name = parse_storage_path(asset.storage_path)
            self.minio.fget_object(bucket_name, object_name, tmp_file_path)

            # Read the content from the temporary file and encode it
            with open(tmp_file_path, "rb") as f:
                encoded_string = base64.b64encode(f.read()).decode('utf-8')
            
            return encoded_string

        finally:
            # Ensure the temporary file is always cleaned up
            if tmp_file_path and os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)


    def _get_existing_analysis(self, asset_id: uuid.UUID, document_id: uuid.UUID) -> DocumentAssetContext | None:
        """Fetches the DocumentAssetContext if an analysis has been completed."""
        return self.db.query(DocumentAssetContext).filter(
            DocumentAssetContext.asset_id == asset_id,
            DocumentAssetContext.document_id == document_id
        ).options(joinedload(DocumentAssetContext.asset)).first()

    def analyze_asset_sync(self, asset_id: uuid.UUID, document_id: uuid.UUID, user_id: uuid.UUID) -> Dict[str, Any]:
        """
        Synchronously analyzes an asset using a VLM and returns the result.
        This version downloads the asset and sends it as a base64 encoded string.
        """
        context = self.db.query(DocumentAssetContext).filter(
            DocumentAssetContext.asset_id == asset_id,
            DocumentAssetContext.document_id == document_id
        ).options(
            joinedload(DocumentAssetContext.asset),
            joinedload(DocumentAssetContext.document).joinedload(Document.knowledge_space)
        ).first()

        if not context or not context.asset or not context.document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset is not associated with the specified document.")

        asset = context.asset
        document = context.document
        
        try:
            asset.analysis_status = AssetAnalysisStatus.IN_PROGRESS
            self.db.commit()

            vlm_client = self.ai_provider_service.get_vlm_client_with_fallback(user_id, document.knowledge_space_id)
            
            base64_image = self._get_asset_base64(asset)
            image_url = f"data:{asset.file_type};base64,{base64_image}"

            response = vlm_client.chat.completions.create(
                model=vlm_client.model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "请详细描述这幅图片的内容。"},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    }
                ],
                max_tokens=1024,
            )
            description = response.choices[0].message.content.strip()

            context.analysis_result = description
            context.model_provider = getattr(vlm_client, 'provider', 'unknown')
            context.model_name = vlm_client.model_name
            asset.analysis_status = AssetAnalysisStatus.COMPLETED
            self.db.commit()

            # After successful analysis, we can directly use get_analysis_result
            analysis_response = self.get_analysis_result(asset_id, document_id)
            if analysis_response:
                return analysis_response
            else:
                # This case should ideally not be reached if analysis was just completed
                raise HTTPException(status_code=500, detail="Failed to retrieve analysis result after completion.")

        except Exception as e:
            asset.analysis_status = AssetAnalysisStatus.FAILED
            self.db.commit()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"VLM analysis failed: {e}")

    def get_asset_by_id(self, asset_id: uuid.UUID) -> Asset:
        """Gets an asset by its UUID, raising an exception if not found."""
        asset = self.db.query(Asset).filter(Asset.id == asset_id).first()
        if not asset:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")
        return asset

    def get_analysis_result(self, asset_id: uuid.UUID, document_id: uuid.UUID) -> schemas.AssetAnalysisResponse | None:
        """
        Gets the analysis status and result for a given asset within a document's context.
        Returns the result if analysis is COMPLETED, otherwise returns None.
        """
        context = self._get_existing_analysis(asset_id, document_id)

        if not context or not context.asset:
            return None

        asset = context.asset
        
        if asset.analysis_status == AssetAnalysisStatus.COMPLETED and context.analysis_result:
            return schemas.AssetAnalysisResponse(
                analysis_status=asset.analysis_status.value,
                description=context.analysis_result,
                model_version=f"{context.model_provider}/{context.model_name}" if context.model_name else None,
                detail="Analysis successfully completed."
            )
        
        # For any other status, we consider the result not ready/available for this endpoint's purpose.
        return None


    def get_assets_by_document_id(self, document_id: uuid.UUID) -> List[Asset]:
        """
        Gets a list of all Asset SQLAlchemy objects associated with a document.
        """
        document = self.db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

        contexts = self.db.query(DocumentAssetContext).options(
            joinedload(DocumentAssetContext.asset)
        ).filter(DocumentAssetContext.document_id == document_id).all()

        if not contexts:
            return []

        return [context.asset for context in contexts if context.asset]

    def get_presigned_url_for_asset(
        self,
        asset_id: uuid.UUID,
        disposition: str = "inline"
    ) -> str:
        """
        Generates a presigned URL for a given asset.
        """
        asset = self.get_asset_by_id(asset_id)

        try:
            bucket_name, object_name = parse_storage_path(asset.storage_path)
            base_name = os.path.basename(object_name)
            response_headers = {
                "response-content-disposition": f'{disposition}; filename="{base_name}"',
                "response-content-type": asset.file_type,
            }
            presigned_url = self.minio.presigned_get_object(
                bucket_name=bucket_name,
                object_name=object_name,
                expires=timedelta(hours=1),
                response_headers=response_headers,
            )
            return presigned_url
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not generate access link for the asset."
            )

    # The `request_analysis` method is deprecated and will be removed.
    # Asset analysis is now exclusively managed by the unified Job system,
    # triggered via the endpoint:
    # POST /documents/{document_id}/jobs/asset-analysis
