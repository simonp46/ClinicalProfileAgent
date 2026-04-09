"""Audit log service."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.domain.enums import AuditActorType
from app.domain.models import AuditLog


class AuditService:
    """Persist auditable actions for traceability."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def log(
        self,
        *,
        actor_type: AuditActorType,
        entity_type: str,
        entity_id: str,
        action: str,
        metadata: dict[str, Any] | None = None,
        actor_id: str | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            actor_type=actor_type,
            actor_id=actor_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            meta=metadata or {},
        )
        self.db.add(entry)
        self.db.flush()
        return entry
