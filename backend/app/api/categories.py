"""
categories.py — list, create, update custom categories (US-14, US-15).
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user_dep
from app.db.session import get_db
from app.models.models import Category, User
from app.schemas.schemas import CategoryCreateRequest, CategoryResponse, CategoryUpdateRequest

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("", response_model=list[CategoryResponse])
async def list_categories(
    current_user: User = Depends(current_user_dep),
    db: AsyncSession = Depends(get_db),
) -> list[CategoryResponse]:
    """Returns global default categories + user's custom categories."""
    result = await db.execute(
        select(Category).where(
            (Category.user_id == current_user.id) | (Category.user_id == None)
        ).order_by(Category.is_default.desc(), Category.name.asc())
    )
    return [CategoryResponse.model_validate(c) for c in result.scalars().all()]


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: CategoryCreateRequest,
    current_user: User = Depends(current_user_dep),
    db: AsyncSession = Depends(get_db),
) -> CategoryResponse:
    cat = Category(user_id=current_user.id, name=payload.name, type=payload.type)
    db.add(cat)
    await db.flush()
    return CategoryResponse.model_validate(cat)


@router.patch("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: uuid.UUID,
    payload: CategoryUpdateRequest,
    current_user: User = Depends(current_user_dep),
    db: AsyncSession = Depends(get_db),
) -> CategoryResponse:
    result = await db.execute(
        select(Category).where(Category.id == category_id, Category.user_id == current_user.id)
    )
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kategori tidak ditemukan.")
    if payload.name is not None:
        cat.name = payload.name
    await db.flush()
    return CategoryResponse.model_validate(cat)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: uuid.UUID,
    current_user: User = Depends(current_user_dep),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(Category).where(Category.id == category_id, Category.user_id == current_user.id)
    )
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kategori tidak ditemukan.")
    await db.delete(cat)
