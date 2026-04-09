from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import Session as SessionModel, Therapist


def test_register_creates_account_and_returns_tokens(client, db_session: Session) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Nuevo Terapeuta",
            "email": "nuevo@clinic.com",
            "password": "supersecure123",
            "google_account_email": "nuevo@workspace.com",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert "access_token" in payload
    assert payload.get("token_type") == "bearer"

    therapist = db_session.scalar(select(Therapist).where(Therapist.email == "nuevo@clinic.com"))
    assert therapist is not None
    assert therapist.full_name == "Nuevo Terapeuta"

    sessions = db_session.scalars(select(SessionModel).where(SessionModel.therapist_id == therapist.id)).all()
    assert len(sessions) >= 3


def test_profile_update_and_upload_endpoints(client, db_session: Session) -> None:
    register = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Perfil Demo",
            "email": "perfil@clinic.com",
            "password": "supersecure123",
        },
    )
    assert register.status_code == 201
    token = register.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    update = client.patch(
        "/api/v1/profile/me",
        json={
            "phone": "+57 300 1112233",
            "contact_email": "contacto@clinic.com",
            "address": "Calle 123 #45-67",
            "profession": "Psicologa clinica",
        },
        headers=headers,
    )
    assert update.status_code == 200
    updated = update.json()
    assert updated["phone"] == "+57 300 1112233"
    assert updated["contact_email"] == "contacto@clinic.com"

    photo_upload = client.post(
        "/api/v1/profile/me/photo",
        headers=headers,
        files={"file": ("photo.png", b"fake-image", "image/png")},
    )
    assert photo_upload.status_code == 200
    assert photo_upload.json()["profile_photo_path"]

    signature_upload = client.post(
        "/api/v1/profile/me/signature",
        headers=headers,
        files={"file": ("signature.png", b"fake-signature", "image/png")},
    )
    assert signature_upload.status_code == 200
    assert signature_upload.json()["signature_image_path"]

    template_upload = client.post(
        "/api/v1/profile/me/template",
        headers=headers,
        files={"file": ("template.pdf", b"%PDF-1.4\n%mock", "application/pdf")},
    )
    assert template_upload.status_code == 200
    template_path = template_upload.json()["template_pdf_path"]
    assert template_path

    asset_response = client.get("/api/v1/profile/me/assets/template-pdf", headers=headers)
    assert asset_response.status_code == 200
    assert "application/pdf" in asset_response.headers.get("content-type", "")

    doc_upload = client.post(
        "/api/v1/profile/me/template",
        headers=headers,
        files={"file": ("template.doc", b"fake-doc", "application/msword")},
    )
    assert doc_upload.status_code == 200
    doc_path = doc_upload.json()["template_docx_path"]
    assert doc_path and doc_path.endswith(".doc")

    docs_upload = client.post(
        "/api/v1/profile/me/template",
        headers=headers,
        files={"file": ("template.docs", b"fake-docs", "application/octet-stream")},
    )
    assert docs_upload.status_code == 200
    docs_path = docs_upload.json()["template_docx_path"]
    assert docs_path and docs_path.endswith(".docs")

    stored_template = Path(docs_path)
    assert stored_template.exists()
    assert len([item for item in stored_template.parent.iterdir() if item.is_file()]) == 1


