"""
audit_service.py — records every sensitive action to audit_logs.

Per CODING_RULES.md §2.7:
- Audit trail is called EXPLICITLY from service layer, not a side effect.
- Audit logs are NEVER rotated or deleted (unlike app logs).
- Distinct from structlog application logs — different purpose.
"""
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import AuditLog


async def log_action(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    action: str,
    entity_type: str,
    source: str,
    entity_id: uuid.UUID | None = None,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    """
    Write one record to audit_logs.

    Called explicitly from transaction_service, auth_service, account_service
    for every create/update/delete/login action.
    """
    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value=old_value,
        new_value=new_value,
        ip_address=ip_address,
        source=source,
    )
    db.add(entry)
    # No flush here — caller owns the transaction boundary.
