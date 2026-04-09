"""Route dependencies."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import CSRFError, decode_token, validate_csrf
from app.db.session import get_db
from app.domain.enums import UserRole
from app.domain.models import Therapist


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_therapist(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Therapist:
    try:
        payload = decode_token(token, expected_type="access")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials") from exc

    therapist_id = str(payload.get("sub"))
    therapist = db.scalar(select(Therapist).where(Therapist.id == therapist_id))
    if therapist is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return therapist


def require_roles(*roles: UserRole):
    def dependency(user: Therapist = Depends(get_current_therapist)) -> Therapist:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient privileges")
        return user

    return dependency


def enforce_csrf_for_refresh(request: Request) -> None:
    csrf_header = request.headers.get("x-csrf-token")
    csrf_cookie = request.cookies.get(settings.csrf_cookie_name)
    try:
        validate_csrf(csrf_header, csrf_cookie)
    except CSRFError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed") from exc
