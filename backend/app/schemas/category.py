"""
Pydantic v2 schemas for categories.
"""

import uuid
from typing import Literal

from pydantic import BaseModel


class CategoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    type: Literal["income", "expense"]
    is_default: bool
    is_active: bool
    user_id: uuid.UUID | None  # None = global default

    model_config = {"from_attributes": True}


class CategoryCreateRequest(BaseModel):
    name: str
    type: Literal["income", "expense"]
