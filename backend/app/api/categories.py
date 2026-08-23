"""
Categories API routes.

GET  /api/categories           — list all categories visible to the user
                                 (global defaults + user's own custom categories)
POST /api/categories           — create a user-specific custom category
DELETE /api/categories/{id}    — soft-delete a user-specific category (is_active=False)
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_active_user
from app.models.category import Category
from app.models.user import User
from app.schemas.category import CategoryCreateRequest, CategoryResponse

router = APIRouter(prefix="/api/categories", tags=["Categories"])


@router.get("", response_model=list[CategoryResponse])
def list_categories(
    type: str | None = None,
    current_user: User = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> list[Category]:
    """
    List all categories visible to the current user:
      - Global defaults (user_id IS NULL)
      - User's own custom categories

    Optionally filter by type: ?type=income or ?type=expense
    """
    stmt = (
        select(Category)
        .where(
            Category.is_active == True,  # noqa: E712
            or_(Category.user_id == None, Category.user_id == current_user.id),  # noqa: E711
        )
        .order_by(Category.is_default.desc(), Category.name)
    )

    if type in ("income", "expense"):
        stmt = stmt.where(Category.type == type)

    return list(db.scalars(stmt))


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    body: CategoryCreateRequest,
    current_user: User = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> Category:
    """Create a custom category scoped to the current user."""
    category = Category(
        id=uuid.uuid4(),
        user_id=current_user.id,
        name=body.name.strip(),
        type=body.type,
        is_default=False,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: uuid.UUID,
    current_user: User = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> None:
    """
    Soft-delete a user-specific category (set is_active=False).
    Cannot delete global default categories.
    """
    category = db.get(Category, category_id)
    if category is None or category.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    if category.is_default:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete a global default category",
        )

    category.is_active = False
    db.commit()
