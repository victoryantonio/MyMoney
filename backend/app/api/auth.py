"""
auth.py — registration, login, token refresh endpoints.
API layer: validates input, calls auth_service, formats response. No business logic.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import auth_service
from app.db.session import get_db
from app.schemas.schemas import (
    RefreshTokenRequest,
    TokenResponse,
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
)
from app.api.deps import current_user_dep
from app.models.models import User

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegisterRequest, db: AsyncSession = Depends(get_db)) -> User:
    try:
        user = await auth_service.register_user(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return user


@router.post("/login", response_model=TokenResponse)
async def login(payload: UserLoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    try:
        _user, tokens = await auth_service.login_user(db, payload.email, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    return tokens


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshTokenRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    try:
        return await auth_service.refresh_tokens(db, payload.refresh_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(current_user_dep)) -> User:
    return current_user
