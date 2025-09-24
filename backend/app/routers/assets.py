import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..models import User, Asset
from ..dependencies import get_current_user, get_asset_service, get_member_or_404
from ..schemas.asset import (
    AssetRead, AssetFilterParams, PaginatedAssetResponse, AssetBulkRequest, AssetBulkDeleteResponse, AssetBulkGetResponse
)
from ..services.asset_service import AssetService

router = APIRouter(
    tags=["Assets"],
)

@router.get(
    "/",
    response_model=PaginatedAssetResponse[AssetRead],
    summary="List and filter assets"
)
def get_assets(
    filters: AssetFilterParams = Depends(AssetFilterParams),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    asset_service: AssetService = Depends(get_asset_service),
):
    """
    Retrieves a paginated and filtered list of assets.
    If a knowledge_space_id is provided, it requires membership in that space.
    If not provided, it returns assets from all knowledge spaces the user is a member of.
    """
    # Conditional Permission Check: 
    # If a specific knowledge space is requested, ensure the user is a member.
    if filters.knowledge_space_id:
        get_member_or_404(filters.knowledge_space_id, db, current_user)

    assets_data, total_count = asset_service.get_assets(
        user_id=current_user.id,
        knowledge_space_id=filters.knowledge_space_id,
        document_id=filters.document_id,
        asset_type=filters.asset_type,
        analysis_status=filters.analysis_status,
        file_types=filters.file_types,
        limit=filters.limit,
        cursor=filters.cursor,
    )

    next_cursor = None
    if len(assets_data) == filters.limit:
        # Assuming the data is sorted by created_at
        next_cursor = assets_data[-1]['created_at'].isoformat()

    return PaginatedAssetResponse(
        items=[AssetRead.model_validate(item) for item in assets_data],
        total_count=total_count,
        next_cursor=next_cursor,
    )

@router.post(
    "/bulk-get",
    response_model=AssetBulkGetResponse,
    summary="Get details for multiple assets by their IDs"
)
def bulk_get_assets(
    payload: AssetBulkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    asset_service: AssetService = Depends(get_asset_service),
):
    """
    Retrieves detailed information for a list of assets, including analysis results.
    All assets must belong to the specified knowledge space, and the user must be a member.
    """
    # Permission Check
    get_member_or_404(payload.knowledge_space_id, db, current_user)

    assets = asset_service.get_assets_by_ids(
        asset_ids=payload.asset_ids,
        knowledge_space_id=payload.knowledge_space_id
    )
    
    return AssetBulkGetResponse(assets=assets)

@router.post(
    "/bulk-download",
    response_class=StreamingResponse,
    summary="Download multiple assets as a zip archive"
)
def bulk_download_assets(
    payload: AssetBulkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    asset_service: AssetService = Depends(get_asset_service),
):
    """
    Downloads a list of assets as a single zip archive.
    All assets must belong to the specified knowledge space, and the user must be a member.
    """
    # Permission Check
    get_member_or_404(payload.knowledge_space_id, db, current_user)

    file_generator = asset_service.create_download_archive(
        asset_ids=payload.asset_ids,
        knowledge_space_id=payload.knowledge_space_id
    )
    
    response_headers = {
        'Content-Disposition': f'attachment; filename="kosmos_assets_{uuid.uuid4()}.zip"'
    }
    
    return StreamingResponse(file_generator, media_type="application/zip", headers=response_headers)

@router.post(
    "/bulk-delete",
    response_model=AssetBulkDeleteResponse,
    summary="Delete multiple assets by their IDs"
)
def bulk_delete_assets(
    payload: AssetBulkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    asset_service: AssetService = Depends(get_asset_service),
):
    """
    Deletes a list of assets by their IDs.
    All assets must belong to the specified knowledge space, and the user must be a member.
    """
    # Permission Check
    get_member_or_404(payload.knowledge_space_id, db, current_user)

    deleted_count = asset_service.delete_assets_by_ids(
        asset_ids=payload.asset_ids,
        knowledge_space_id=payload.knowledge_space_id
    )
    
    return AssetBulkDeleteResponse(deleted_count=deleted_count)

@router.get(
    "/{asset_id}",
    response_model=AssetRead,
    summary="Get a single asset by its ID"
)
def get_asset(
    asset_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    asset_service: AssetService = Depends(get_asset_service),
):
    """
    Retrieves the details of a single asset.
    """
    asset = asset_service.get_asset_by_id(asset_id)
    # Permission Check
    get_member_or_404(asset.knowledge_space_id, db, current_user)
    return asset