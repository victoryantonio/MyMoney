"""
Categories API routes.

GET  /api/categories           — list all categories visible to the user
                                 (global defaults + user's own custom categories)
POST /api/categories           — create a user-specific custom category
PUT  /api/categories/{id}      — rename and/or re-type a user-specific category
DELETE /api/categories/{id}    — soft-delete a category. Global defaults are
                                 "shadowed" per-user (is_active=False row milik
                                 user) sehingga hanya user tsb yang tidak
                                 melihatnya lagi; user lain tetap melihat default.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_active_user
from app.core.audit_service import record_audit
from app.models.category import Category, category_visible_clause
from app.models.profile import Profile
from app.schemas.category import (
    CategoryCreateRequest,
    CategoryResponse,
    CategoryUpdateRequest,
)

router = APIRouter(prefix="/api/categories", tags=["Categories"])


def _find_visible_duplicate(
    db: Session,
    user_id: uuid.UUID,
    name: str,
    type: str,
    exclude_id: uuid.UUID | None = None,
) -> Category | None:
    """
    Case-insensitive duplicate lookup across the categories VISIBLE to this
    user (category_visible_clause: aktif, milik user atau global yang tidak
    di-shadow oleh user). Mencegah kategori custom membayangi default global
    dengan nama yang sama dan melindungi unique index
    idx_categories_user_name_type (DATABASE.md §2.3).
    """
    stmt = select(Category).where(
        func.lower(Category.name) == name.lower(),
        Category.type == type,
        category_visible_clause(user_id),
    )
    if exclude_id is not None:
        stmt = stmt.where(Category.id != exclude_id)
    return db.scalar(stmt)


@router.get("", response_model=list[CategoryResponse])
def list_categories(
    type: str | None = None,
    current_user: Profile = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> list[Category]:
    """
    List all categories visible to the current user:
      - Global defaults (user_id IS NULL) yang belum di-shadow user ini
      - User's own custom categories

    Optionally filter by type: ?type=income | ?type=expense | ?type=transfer
    """
    stmt = (
        select(Category)
        .where(category_visible_clause(current_user.id))
        .order_by(Category.is_default.desc(), Category.name)
    )

    if type in ("income", "expense", "transfer"):
        stmt = stmt.where(Category.type == type)

    return list(db.scalars(stmt))


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    body: CategoryCreateRequest,
    current_user: Profile = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> Category:
    """Create a custom category scoped to the current user."""
    name = body.name.strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Category name must not be empty",
        )
    if _find_visible_duplicate(db, current_user.id, name, body.type) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Category '{name}' already exists",
        )

    category = Category(
        id=uuid.uuid4(),
        user_id=current_user.id,
        name=name,
        type=body.type,
        is_default=False,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.put("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: uuid.UUID,
    body: CategoryUpdateRequest,
    current_user: Profile = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> Category:
    """
    Update a user-specific category (name and/or type — PATCH semantics).
    Global default categories are immutable (403). Renaming preserves
    historical transactions (they reference category_id, not the name).
    """
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    # Global defaults are immutable for everyone (they are user_id IS NULL,
    # so they must be checked before the ownership check below).
    if category.is_default:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot edit a global default category",
        )

    if category.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    new_name = body.name.strip() if body.name is not None else category.name
    if not new_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Category name must not be empty",
        )
    new_type = body.type if body.type is not None else category.type

    dup = _find_visible_duplicate(db, current_user.id, new_name, new_type, exclude_id=category.id)
    if dup is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Category '{new_name}' already exists",
        )

    old_value = {"name": category.name, "type": category.type}
    category.name = new_name
    category.type = new_type
    record_audit(
        db,
        user_id=current_user.id,
        action="update",
        entity_type="category",
        entity_id=category.id,
        old_value=old_value,
        new_value={"name": new_name, "type": new_type},
        source="app",
    )
    db.commit()
    db.refresh(category)
    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: uuid.UUID,
    current_user: Profile = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> None:
    """
    Soft-delete sebuah kategori yang terlihat oleh user ini.

    - Kategori milik user → is_active=False (transaksi lama tetap tersimpan;
      kategori tidak bisa dipilih lagi).
    - Default global (user_id IS NULL) → buat baris "shadow" milik user
      (is_active=False, nama/type sama). User lain tetap melihat default;
      user ini tidak melihatnya lagi (category_visible_clause). Tidak pernah
      menghapus baris global agar user lain tidak terpengaruh.
    """
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    if category.user_id != current_user.id:
        # Default global → shadow per-user.
        if category.is_default and category.user_id is None:
            existing_shadow = db.scalar(
                select(Category).where(
                    Category.user_id == current_user.id,
                    Category.is_active == False,  # noqa: E712
                    func.lower(Category.name) == category.name.lower(),
                    Category.type == category.type,
                )
            )
            if existing_shadow is None:
                shadow = Category(
                    id=uuid.uuid4(),
                    user_id=current_user.id,
                    name=category.name,
                    type=category.type,
                    is_default=False,
                    is_active=False,
                )
                db.add(shadow)
                record_audit(
                    db,
                    user_id=current_user.id,
                    action="delete",
                    entity_type="category",
                    entity_id=category.id,
                    old_value={
                        "name": category.name,
                        "type": category.type,
                        "is_default": True,
                    },
                    new_value={"is_active": False, "note": "global default shadowed per-user"},
                    source="app",
                )
                db.commit()
            return None
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    old_value = {"name": category.name, "type": category.type}
    category.is_active = False
    record_audit(
        db,
        user_id=current_user.id,
        action="delete",
        entity_type="category",
        entity_id=category.id,
        old_value=old_value,
        new_value={"is_active": False},
        source="app",
    )
    db.commit()
    return None
