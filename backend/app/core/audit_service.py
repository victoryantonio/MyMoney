"""
Audit trail service (CODING_RULES §2.6).

Every mutating operation writes an AuditLog row explicitly from the service
layer. Logs are never deleted. `action` and `source` are constrained by DB
CHECK constraints — see models/audit_log.py.
"""

import structlog
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog

log = structlog.get_logger()

VALID_ACTIONS = {"create", "update", "delete", "login", "login_failed"}
VALID_SOURCES = {"telegram", "app"}


def record_audit(
    db: Session,
    *,
    user_id: int,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    old_value: dict | None = None,
    new_value: dict | None = None,
    source: str = "app",
    ip_address: str | None = None,
) -> None:
    """Insert an audit row. Values are serialized to JSONB by the model."""
    if action not in VALID_ACTIONS:
        raise ValueError(f"invalid audit action: {action!r}")
    if source not in VALID_SOURCES:
        raise ValueError(f"invalid audit source: {source!r}")

    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value=old_value,
        new_value=new_value,
        source=source,
        ip_address=ip_address,
    )
    db.add(entry)
    db.flush()  # assign id without committing; caller owns the commit
    log.info(
        "audit_recorded",
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        source=source,
    )
