"""Therapist profile routes."""

from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path
from typing import Literal
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.deps import get_current_therapist
from app.application.services.audit_service import AuditService
from app.application.services.auth_service import AuthService
from app.application.services.google_oauth_service import GoogleOAuthService
from app.application.services.microsoft_oauth_service import MicrosoftOAuthService
from app.core.config import settings
from app.db.session import get_db
from app.domain.enums import AuditActorType, DocumentStatus
from app.domain.models import GeneratedDocument, Therapist
from app.domain.models import Session as SessionModel
from app.domain.schemas import GoogleConnectUrlOut, TherapistProfileOut, TherapistProfileUpdate

router = APIRouter(prefix="/profile", tags=["profile"])

_ALLOWED_PHOTO_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
_ALLOWED_SIGNATURE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
_ALLOWED_TEMPLATE_CONTENT_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
_ALLOWED_TEMPLATE_EXTENSIONS = {".pdf", ".doc", ".docx", ".docs"}


@router.get("/me", response_model=TherapistProfileOut)
def get_profile_me(current_user: Therapist = Depends(get_current_therapist)) -> dict:
    return _serialize_profile(current_user)


@router.patch("/me", response_model=TherapistProfileOut)
def update_profile_me(
    payload: TherapistProfileUpdate,
    db: Session = Depends(get_db),
    current_user: Therapist = Depends(get_current_therapist),
) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    if "google_account_email" in updates and updates["google_account_email"] is not None:
        updates["google_account_email"] = str(updates["google_account_email"])
    if "contact_email" in updates and updates["contact_email"] is not None:
        updates["contact_email"] = str(updates["contact_email"])

    auth = AuthService(db)
    therapist = auth.update_therapist_profile(current_user, updates)

    _log_profile_update(
        db,
        actor_id=current_user.id,
        action="therapist.profile_updated",
        metadata={"updated_fields": sorted(updates.keys())},
    )

    db.commit()
    db.refresh(therapist)
    return _serialize_profile(therapist)


@router.post("/me/google/connect", response_model=GoogleConnectUrlOut)
def connect_google_account(
    db: Session = Depends(get_db),
    current_user: Therapist = Depends(get_current_therapist),
) -> GoogleConnectUrlOut:
    service = GoogleOAuthService(db)
    authorization_url = service.build_authorization_url(current_user)
    _log_profile_update(
        db,
        actor_id=current_user.id,
        action="therapist.google_oauth_started",
        metadata={"google_account_email": current_user.google_account_email},
    )
    db.commit()
    return GoogleConnectUrlOut(authorization_url=authorization_url)


@router.post("/me/google/disconnect", response_model=TherapistProfileOut)
def disconnect_google_account(
    db: Session = Depends(get_db),
    current_user: Therapist = Depends(get_current_therapist),
) -> dict:
    service = GoogleOAuthService(db)
    therapist = service.disconnect(current_user)
    _log_profile_update(
        db,
        actor_id=current_user.id,
        action="therapist.google_oauth_disconnected",
        metadata={},
    )
    db.commit()
    db.refresh(therapist)
    return _serialize_profile(therapist)


@router.get("/google/callback")
def google_oauth_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if error:
        return _redirect_profile("google", "error", reason=error)
    if not code or not state:
        return _redirect_profile("google", "error", reason="missing_code")

    service = GoogleOAuthService(db)
    try:
        therapist, result = service.complete_authorization(code=code, state=state)
        _log_profile_update(
            db,
            actor_id=therapist.id,
            action="therapist.google_oauth_connected",
            metadata={
                "connected_email": result.connected_email,
                "granted_scopes": result.granted_scopes,
            },
        )
        db.commit()
        return _redirect_profile("google", "connected")
    except HTTPException as exc:
        db.rollback()
        return _redirect_profile("google", "error", reason=str(exc.detail))
    except Exception:
        db.rollback()
        return _redirect_profile("google", "error", reason="oauth_callback_failed")


@router.post("/me/microsoft/connect", response_model=GoogleConnectUrlOut)
def connect_microsoft_account(
    db: Session = Depends(get_db),
    current_user: Therapist = Depends(get_current_therapist),
) -> GoogleConnectUrlOut:
    service = MicrosoftOAuthService(db)
    authorization_url = service.build_authorization_url(current_user)
    _log_profile_update(
        db,
        actor_id=current_user.id,
        action="therapist.microsoft_oauth_started",
        metadata={"microsoft_account_email": current_user.microsoft_account_email},
    )
    db.commit()
    return GoogleConnectUrlOut(authorization_url=authorization_url)


@router.post("/me/microsoft/disconnect", response_model=TherapistProfileOut)
def disconnect_microsoft_account(
    db: Session = Depends(get_db),
    current_user: Therapist = Depends(get_current_therapist),
) -> dict:
    service = MicrosoftOAuthService(db)
    therapist = service.disconnect(current_user)
    _log_profile_update(
        db,
        actor_id=current_user.id,
        action="therapist.microsoft_oauth_disconnected",
        metadata={},
    )
    db.commit()
    db.refresh(therapist)
    return _serialize_profile(therapist)


@router.get("/microsoft/callback")
def microsoft_oauth_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if error:
        return _redirect_profile("microsoft", "error", reason=error)
    if not code or not state:
        return _redirect_profile("microsoft", "error", reason="missing_code")

    service = MicrosoftOAuthService(db)
    try:
        therapist, result = service.complete_authorization(code=code, state=state)
        _log_profile_update(
            db,
            actor_id=therapist.id,
            action="therapist.microsoft_oauth_connected",
            metadata={
                "connected_email": result.connected_email,
                "granted_scopes": result.granted_scopes,
            },
        )
        db.commit()
        return _redirect_profile("microsoft", "connected")
    except HTTPException as exc:
        db.rollback()
        return _redirect_profile("microsoft", "error", reason=str(exc.detail))
    except Exception:
        db.rollback()
        return _redirect_profile("microsoft", "error", reason="oauth_callback_failed")


@router.post("/me/photo", response_model=TherapistProfileOut)
def upload_profile_photo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Therapist = Depends(get_current_therapist),
) -> dict:
    _ensure_content_type(file, _ALLOWED_PHOTO_CONTENT_TYPES, "Foto de perfil")
    _clear_previous_profile_assets(current_user.id, category="photo")
    stored_path = _store_uploaded_file(current_user.id, file=file, category="photo")
    current_user.profile_photo_path = stored_path
    db.add(current_user)

    _log_profile_update(
        db,
        actor_id=current_user.id,
        action="therapist.profile_photo_uploaded",
        metadata={"path": stored_path},
    )

    db.commit()
    db.refresh(current_user)
    return _serialize_profile(current_user)


@router.post("/me/signature", response_model=TherapistProfileOut)
def upload_signature(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Therapist = Depends(get_current_therapist),
) -> dict:
    _ensure_content_type(file, _ALLOWED_SIGNATURE_CONTENT_TYPES, "Firma")
    _clear_previous_profile_assets(current_user.id, category="signature")
    stored_path = _store_uploaded_file(current_user.id, file=file, category="signature")
    current_user.signature_image_path = stored_path
    db.add(current_user)

    _log_profile_update(
        db,
        actor_id=current_user.id,
        action="therapist.signature_uploaded",
        metadata={"path": stored_path},
    )

    db.commit()
    db.refresh(current_user)
    return _serialize_profile(current_user)


@router.post("/me/template", response_model=TherapistProfileOut)
def upload_template(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Therapist = Depends(get_current_therapist),
) -> dict:
    _ensure_template_file(file)
    _clear_previous_profile_assets(current_user.id, category="template")
    stored_path = _store_uploaded_file(current_user.id, file=file, category="template")

    extension = Path(file.filename or "").suffix.lower()
    is_pdf = file.content_type == "application/pdf" or extension == ".pdf"

    templates_dir = Path(__file__).resolve().parents[3] / "assets" / "templates"
    default_respiro_pdf = templates_dir / "plantilla_historia_clinica_respira_integral_of.pdf"

    if is_pdf:
        current_user.template_pdf_path = stored_path
        current_user.template_docx_path = None
    else:
        current_user.template_docx_path = stored_path
        current_user.template_pdf_path = (
            str(default_respiro_pdf) if default_respiro_pdf.exists() else None
        )

    invalidated_docs = _invalidate_generated_exports(db, therapist_id=current_user.id)
    db.add(current_user)
    _log_profile_update(
        db,
        actor_id=current_user.id,
        action="therapist.template_uploaded",
        metadata={
            "path": stored_path,
            "content_type": file.content_type,
            "invalidated_documents": invalidated_docs,
        },
    )

    db.commit()
    db.refresh(current_user)
    return _serialize_profile(current_user)


@router.get("/me/assets/{asset_type}")
def get_profile_asset(
    asset_type: Literal["photo", "signature", "template-pdf", "template-docx"],
    db: Session = Depends(get_db),
    current_user: Therapist = Depends(get_current_therapist),
) -> FileResponse:
    _ = db
    file_path = _resolve_asset_path(current_user, asset_type)

    if file_path is None or not Path(file_path).exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archivo no encontrado")

    guessed_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    file_name = Path(file_path).name
    return FileResponse(path=file_path, media_type=guessed_type, filename=file_name)


def _serialize_profile(therapist: Therapist) -> dict:
    return {
        "id": therapist.id,
        "full_name": therapist.full_name,
        "email": therapist.email,
        "role": therapist.role,
        "google_account_email": therapist.google_account_email,
        "google_oauth_connected": bool(therapist.google_oauth_refresh_token),
        "google_oauth_email": therapist.google_oauth_subject,
        "microsoft_account_email": therapist.microsoft_account_email,
        "microsoft_oauth_connected": bool(therapist.microsoft_oauth_refresh_token),
        "microsoft_oauth_email": therapist.microsoft_oauth_subject,
        "phone": therapist.phone,
        "contact_email": therapist.contact_email,
        "address": therapist.address,
        "profession": therapist.profession,
        "profile_photo_path": therapist.profile_photo_path,
        "signature_image_path": therapist.signature_image_path,
        "template_pdf_path": therapist.template_pdf_path,
        "template_docx_path": therapist.template_docx_path,
        "created_at": therapist.created_at,
        "updated_at": therapist.updated_at,
    }


def _redirect_profile(
    provider: str, status_value: str, *, reason: str | None = None
) -> RedirectResponse:
    base = settings.web_app_url.rstrip("/") + "/profile"
    separator = "?" if "?" not in base else "&"
    url = f"{base}{separator}{provider}={status_value}"
    if reason:
        url = f"{url}&reason={quote_plus(reason)}"
    return RedirectResponse(url)


def _ensure_template_file(file: UploadFile) -> None:
    extension = Path(file.filename or "").suffix.lower()
    content_type = (file.content_type or "").lower()

    if content_type in _ALLOWED_TEMPLATE_CONTENT_TYPES:
        return

    if extension in _ALLOWED_TEMPLATE_EXTENSIONS:
        return

    allowed_types = ", ".join(sorted(_ALLOWED_TEMPLATE_CONTENT_TYPES))
    allowed_ext = ", ".join(sorted(_ALLOWED_TEMPLATE_EXTENSIONS))
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            "Plantilla invalida. Tipos permitidos: "
            f"{allowed_types}. Extensiones permitidas: {allowed_ext}"
        ),
    )


def _ensure_content_type(file: UploadFile, allowed: set[str], label: str) -> None:
    if file.content_type not in allowed:
        allowed_list = ", ".join(sorted(allowed))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{label} invalida. Tipos permitidos: {allowed_list}",
        )


def _clear_previous_profile_assets(therapist_id: str, *, category: str) -> None:
    storage_dir = Path(settings.artifacts_dir) / "profiles" / therapist_id / category
    if not storage_dir.exists():
        return

    for entry in storage_dir.iterdir():
        if entry.is_file():
            entry.unlink(missing_ok=True)


def _store_uploaded_file(therapist_id: str, *, file: UploadFile, category: str) -> str:
    storage_dir = Path(settings.artifacts_dir) / "profiles" / therapist_id / category
    storage_dir.mkdir(parents=True, exist_ok=True)

    extension = Path(file.filename or "").suffix.lower()
    if not extension:
        extension = _extension_from_content_type(file.content_type)

    file_name = f"{uuid.uuid4().hex}{extension}"
    destination = storage_dir / file_name

    data = file.file.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo esta vacio")

    destination.write_bytes(data)
    return str(destination)


def _extension_from_content_type(content_type: str | None) -> str:
    mapping = {
        "application/pdf": ".pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "application/msword": ".doc",
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }
    if content_type in mapping:
        return mapping[content_type]
    return ""


def _resolve_asset_path(current_user: Therapist, asset_type: str) -> str | None:
    if asset_type == "photo":
        return current_user.profile_photo_path
    if asset_type == "signature":
        return current_user.signature_image_path
    if asset_type == "template-pdf":
        return current_user.template_pdf_path
    if asset_type == "template-docx":
        return current_user.template_docx_path
    return None


def _invalidate_generated_exports(db: Session, *, therapist_id: str) -> int:
    documents = db.scalars(
        select(GeneratedDocument)
        .join(SessionModel, GeneratedDocument.session_id == SessionModel.id)
        .where(SessionModel.therapist_id == therapist_id)
    ).all()

    invalidated = 0
    for document in documents:
        had_export = bool(document.exported_pdf_path or document.exported_docx_path)
        if not had_export:
            continue

        document.exported_pdf_path = None
        document.exported_pdf_mime_type = None
        document.exported_docx_path = None
        document.exported_docx_mime_type = None
        if document.status == DocumentStatus.exported:
            document.status = DocumentStatus.created

        db.add(document)
        invalidated += 1

    return invalidated


def _log_profile_update(
    db: Session,
    *,
    actor_id: str,
    action: str,
    metadata: dict[str, object],
) -> None:
    audit = AuditService(db)
    audit.log(
        actor_type=AuditActorType.therapist,
        actor_id=actor_id,
        entity_type="therapist",
        entity_id=actor_id,
        action=action,
        metadata=metadata,
    )
