from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import JWTError

from ..core import security
from ..core.db import get_db
from ..schemas.token import Token, AccessToken
from ..services import user_service

router = APIRouter(
    tags=["Authentication"]
)

@router.post("/token", response_model=Token)
def login_for_access_token(
    db: Session = Depends(get_db), 
    form_data: OAuth2PasswordRequestForm = Depends()
):
    """
    使用用户名和密码进行身份验证，并返回Access Token和Refresh Token。
    """
    user = user_service.authenticate_user(
        db=db, identifier=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = security.create_access_token(user)
    refresh_token = security.create_refresh_token(db, user_id=user.id)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@router.post("/token/refresh", response_model=AccessToken)
def refresh_access_token(
    refresh_token: str = Body(..., embed=True),
    db: Session = Depends(get_db)
):
    """
    使用一个有效的Refresh Token来获取一个新的Access Token。
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        user = security.get_user_from_refresh_token(db, token=refresh_token)
        if not user:
            raise credentials_exception
        
        new_access_token = security.create_access_token(user)
        return {"access_token": new_access_token, "token_type": "bearer"}

    except JWTError as e:
        raise credentials_exception from e
