from fastapi import Security, HTTPException, Header
from fastapi.security.api_key import APIKeyHeader
from starlette import status
from .core.config import settings

API_KEY_HEADER = APIKeyHeader(name="X-Internal-Secret", auto_error=False)

async def get_internal_api_key(
    api_key_header: str = Security(API_KEY_HEADER),
    x_internal_secret: str = Header(None, alias="X-Internal-Secret")
):
    """
    Dependency to authenticate requests to the internal API.
    Checks for a secret key in the request header.
    """
    # The header can be passed in two ways, this handles both.
    secret = api_key_header or x_internal_secret
    
    if not secret or secret != settings.INTERNAL_API_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    return secret
