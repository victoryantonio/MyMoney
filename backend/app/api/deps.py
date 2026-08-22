"""
FastAPI dependency — extracts and validates Bearer token, returns current User.
API layer only: no business logic here.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.auth_service import get_current_user
from app.models.models import User

bearer_scheme = HTTPBearer()


async def current_user_dep(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency: validate JWT and return User."""
    try:
        return await get_current_user(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
