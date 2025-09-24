from fastapi import Depends, HTTPException, status, Path, Query
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError, jwt
import uuid
import redis
from minio import Minio

from .core.db import get_db
from .core.config import settings
from .core.object_storage import get_minio_client
from .core.redis_client import get_redis_client
from .schemas.token import TokenData
from .models import User, KnowledgeSpaceMember, Document, Asset, DocumentAssetContext
from .services.asset_service import AssetService
from .services.reading_service import ReadingService
from .services import JobService
from .services.bookmark_service import BookmarkService
from .services.grep.grep_service import GrepService
from typing import List

from .services.ai_provider_service import AIProviderService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

# --- Service Dependencies ---

def get_ai_provider_service(
    db: Session = Depends(get_db),
) -> "AIProviderService":
    """Dependency to get an instance of AIProviderService."""
    from .services.ai_provider_service import AIProviderService
    return AIProviderService(db=db)

def get_asset_service(
    db: Session = Depends(get_db),
    minio: Minio = Depends(get_minio_client),
    redis_cache: redis.Redis = Depends(get_redis_client),
    ai_provider_service: "AIProviderService" = Depends(get_ai_provider_service)
) -> AssetService:
    return AssetService(db=db, minio=minio, redis_cache=redis_cache, ai_provider_service=ai_provider_service)

def get_reading_service(
    db: Session = Depends(get_db),
    minio: Minio = Depends(get_minio_client),
) -> ReadingService:
    """Dependency to get an instance of ReadingService."""
    return ReadingService(db=db, minio=minio)

def get_grep_service(
    db: Session = Depends(get_db),
    minio: Minio = Depends(get_minio_client),
) -> GrepService:
    """Dependency to get an instance of GrepService."""
    return GrepService(db=db, minio=minio)

def get_job_service(
    db: Session = Depends(get_db),
    redis_cache: redis.Redis = Depends(get_redis_client),
    minio: Minio = Depends(get_minio_client),
) -> JobService:
    """Dependency to get an instance of JobService."""
    return JobService(db=db, redis_client=redis_cache, minio_client=minio)

def get_bookmark_service(db: Session = Depends(get_db)) -> BookmarkService:
    """Dependency to get an instance of BookmarkService."""
    return BookmarkService(db=db)

def get_asset_analysis_service(
    db: Session = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_client),
    minio_client: Minio = Depends(get_minio_client),
    ai_provider_service: "AIProviderService" = Depends(get_ai_provider_service),
) -> "AssetAnalysisService":
    """Dependency to get an instance of AssetAnalysisService."""
    from .services.asset_analysis_service import AssetAnalysisService
    return AssetAnalysisService(
        db=db,
        redis_client=redis_client,
        minio_client=minio_client,
        ai_provider_service=ai_provider_service
    )

from .services.ingestion.service import IngestionService

def get_ingestion_service(
    db: Session = Depends(get_db),
    minio: Minio = Depends(get_minio_client),
    job_service: JobService = Depends(get_job_service),
) -> IngestionService:
    """Dependency to get an instance of IngestionService."""
    return IngestionService(db=db, minio=minio, job_service=job_service)

# --- Authentication and Authorization Dependencies ---

def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    """Dependency to get the current user from a JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception

        try:
            # The application layer should work with UUID objects.
            user_id = uuid.UUID(user_id_str)
        except ValueError:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    # With the custom UUID TypeDecorator, the ORM can handle the comparison directly.
    user = db.query(User).filter(User.id == user_id).first()
    
    if user is None:
        raise credentials_exception
    return user

def get_member_or_404(
    knowledge_space_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> KnowledgeSpaceMember:
    """
    Dependency to check if the current user is a member of the knowledge space.
    Returns the membership object if they are, otherwise raises a 404.
    """
    membership = db.query(KnowledgeSpaceMember).filter(
        KnowledgeSpaceMember.knowledge_space_id == knowledge_space_id,
        KnowledgeSpaceMember.user_id == current_user.id
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge space not found or you are not a member",
        )
    return membership

def require_role(allowed_roles: List[str]):
    """Dependency factory that returns a dependency to check for required roles."""
    def role_checker(
        membership: KnowledgeSpaceMember = Depends(get_member_or_404),
    ) -> KnowledgeSpaceMember:
        if membership.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires one of the following roles: {', '.join(allowed_roles)}",
            )
        return membership
    return role_checker

def require_super_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to ensure the current user has the 'super_admin' role."""
    if current_user.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This operation requires super admin privileges",
        )
    return current_user

# --- Resource-specific Dependencies ---

def get_document_and_verify_membership(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Document:
    """
    Dependency to get a document by its ID and verify the current user is a member
    of the knowledge space it belongs to.
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    get_member_or_404(knowledge_space_id=document.knowledge_space_id, db=db, current_user=current_user)
    return document

def get_asset_and_verify_membership(
    asset_id: uuid.UUID = Path(..., description="The UUID of the asset."),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Asset:
    """
    Dependency to get an asset by its UUID and verify the user has access to it
    through their knowledge space membership.
    """
    # This query joins from Asset -> DocumentAssetContext -> Document -> KnowledgeSpaceMember
    # to ensure the asset is connected to a document the user has access to.
    query = db.query(Asset).join(
        Asset.document_contexts
    ).join(
        DocumentAssetContext.document
    ).join(
        Document.knowledge_space
    ).join(
        KnowledgeSpaceMember,
        KnowledgeSpaceMember.knowledge_space_id == Document.knowledge_space_id
    ).filter(
        Asset.id == asset_id,
        KnowledgeSpaceMember.user_id == current_user.id
    )

    asset = query.first()

    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found or you do not have permission to access it."
        )
    return asset
