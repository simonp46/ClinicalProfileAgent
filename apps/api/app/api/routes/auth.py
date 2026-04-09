"""Authentication routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.routes.deps import enforce_csrf_for_refresh, get_current_therapist
from app.application.services.auth_service import AuthService
from app.application.services.demo_onboarding_service import DemoOnboardingService
from app.core.config import settings
from app.domain.models import Therapist
from app.domain.schemas import AuthLoginRequest, AuthRegisterRequest, TherapistProfileOut, TokenPair
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenPair)
def login(payload: AuthLoginRequest, response: Response, db: Session = Depends(get_db)) -> TokenPair:
    auth = AuthService(db)
    therapist = auth.authenticate(payload.email, payload.password)
    if therapist is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales invalidas")

    access_token, refresh_token, csrf_token = auth.build_login_tokens(therapist)
    db.commit()
    _set_auth_cookies(response, refresh_token=refresh_token, csrf_token=csrf_token)
    return TokenPair(access_token=access_token, csrf_token=csrf_token)


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
def register(payload: AuthRegisterRequest, response: Response, db: Session = Depends(get_db)) -> TokenPair:
    if len(payload.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contrasena debe tener al menos 8 caracteres",
        )

    auth = AuthService(db)
    try:
        therapist = auth.register_therapist(
            full_name=payload.full_name,
            email=str(payload.email),
            password=payload.password,
            google_account_email=str(payload.google_account_email) if payload.google_account_email else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    try:
        demo_onboarding = DemoOnboardingService(db)
        demo_onboarding.ensure_demo_sessions_for_therapist(therapist)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudieron crear sesiones demo para el nuevo usuario",
        ) from exc

    access_token, refresh_token, csrf_token = auth.build_login_tokens(therapist)
    db.commit()
    _set_auth_cookies(response, refresh_token=refresh_token, csrf_token=csrf_token)
    return TokenPair(access_token=access_token, csrf_token=csrf_token)


@router.post("/refresh", response_model=TokenPair)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)) -> TokenPair:
    enforce_csrf_for_refresh(request)
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    auth = AuthService(db)
    therapist = auth.validate_refresh(refresh_token)
    if therapist is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token invalido")

    auth.revoke_refresh(refresh_token)
    access_token, new_refresh_token, csrf_token = auth.build_login_tokens(therapist)
    db.commit()

    _set_auth_cookies(response, refresh_token=new_refresh_token, csrf_token=csrf_token)
    return TokenPair(access_token=access_token, csrf_token=csrf_token)


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> dict[str, str]:
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    if refresh_token:
        auth = AuthService(db)
        auth.revoke_refresh(refresh_token)
        db.commit()

    response.delete_cookie(settings.refresh_cookie_name)
    response.delete_cookie(settings.csrf_cookie_name)
    return {"status": "ok"}


@router.get("/me", response_model=TherapistProfileOut)
def me(current_user: Therapist = Depends(get_current_therapist)) -> TherapistProfileOut:
    return TherapistProfileOut.model_validate(current_user)


def _set_auth_cookies(response: Response, *, refresh_token: str, csrf_token: str) -> None:
    max_age_seconds = settings.jwt_refresh_token_expire_days * 24 * 3600

    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=max_age_seconds,
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        httponly=False,
        secure=False,
        samesite="lax",
        max_age=max_age_seconds,
    )
