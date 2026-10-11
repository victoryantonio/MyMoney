"""
Schemas for `/api/profile` — setelan profil yang tidak disimpan di Supabase Auth.

Hanya field yang memang boleh diubah user dari aplikasi yang diekspos
(`display_name`, `timezone`). Email/password dikelola Supabase Auth.
"""

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator


class ProfileResponse(BaseModel):
    display_name: str
    timezone: str
    timezone_confirmed: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ProfileUpdateRequest(BaseModel):
    """Partial update — field yang tidak dikirim tidak diubah."""

    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)

    @field_validator("display_name")
    @classmethod
    def _strip_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stripped = v.strip()
        if not stripped:
            raise ValueError("display_name tidak boleh kosong")
        return stripped

    @field_validator("timezone")
    @classmethod
    def _validate_timezone(cls, v: str | None) -> str | None:
        """Tolak nama timezone IANA yang tidak dikenal (mis. 'Jakarta/Asia')."""
        if v is None:
            return None
        candidate = v.strip()
        try:
            ZoneInfo(candidate)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"timezone tidak dikenal: {candidate}") from exc
        return candidate
