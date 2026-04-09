"""Risk flag routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.deps import get_current_therapist
from app.db.session import get_db
from app.domain.models import RiskFlag, Therapist

router = APIRouter(prefix="/risk-flags", tags=["risk-flags"])


@router.get("")
def list_risk_flags(
    session_id: str | None = None,
    db: Session = Depends(get_db),
    _: Therapist = Depends(get_current_therapist),
) -> dict:
    query = select(RiskFlag).order_by(RiskFlag.created_at.desc())
    if session_id:
        query = query.where(RiskFlag.session_id == session_id)
    items = db.scalars(query).all()
    return {
        "items": [
            {
                "id": item.id,
                "session_id": item.session_id,
                "severity": item.severity.value,
                "category": item.category.value,
                "snippet": item.snippet,
                "rationale": item.rationale,
                "requires_human_review": item.requires_human_review,
                "created_at": item.created_at.isoformat(),
            }
            for item in items
        ]
    }