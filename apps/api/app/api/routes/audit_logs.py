"""Audit log routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.deps import get_current_therapist
from app.db.session import get_db
from app.domain.models import AuditLog, Therapist

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


@router.get("")
def list_audit_logs(
    entity_type: str | None = None,
    entity_id: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: Therapist = Depends(get_current_therapist),
) -> dict:
    query = select(AuditLog)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.where(AuditLog.entity_id == entity_id)
    query = query.order_by(AuditLog.created_at.desc()).limit(limit)

    items = db.scalars(query).all()
    return {
        "items": [
            {
                "id": item.id,
                "actor_type": item.actor_type.value,
                "actor_id": item.actor_id,
                "entity_type": item.entity_type,
                "entity_id": item.entity_id,
                "action": item.action,
                "metadata": item.meta,
                "created_at": item.created_at.isoformat(),
            }
            for item in items
        ]
    }
