from types import SimpleNamespace

from app.application.services.auth_service import EmailDeliveryAdapter


def test_password_reset_flow_updates_password(client, db_session, monkeypatch) -> None:
    sent = {}

    def _send(self, *, recipient: str, full_name: str | None, code: str):
        sent["recipient"] = recipient
        sent["code"] = code
        return SimpleNamespace(
            delivered=True, destination=recipient, subject="reset", artifact_path=None
        )

    monkeypatch.setattr(EmailDeliveryAdapter, "send_password_reset_code", _send)

    register = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Reset Demo",
            "email": "reset@clinic.com",
            "password": "secret123",
        },
    )
    assert register.status_code == 201

    request_reset = client.post(
        "/api/v1/auth/request-password-reset",
        json={"email": "reset@clinic.com"},
    )
    assert request_reset.status_code == 200
    assert sent["recipient"] == "reset@clinic.com"

    reset = client.post(
        "/api/v1/auth/reset-password",
        json={
            "email": "reset@clinic.com",
            "code": sent["code"],
            "new_password": "newsecret123",
        },
    )
    assert reset.status_code == 200

    old_login = client.post(
        "/api/v1/auth/login",
        json={"email": "reset@clinic.com", "password": "secret123"},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/v1/auth/login",
        json={"email": "reset@clinic.com", "password": "newsecret123"},
    )
    assert new_login.status_code == 200


def test_password_reset_request_is_generic_for_unknown_email(client, monkeypatch) -> None:
    def _send(self, *, recipient: str, full_name: str | None, code: str):
        raise AssertionError("No se debe enviar correo para usuarios inexistentes")

    monkeypatch.setattr(EmailDeliveryAdapter, "send_password_reset_code", _send)

    response = client.post(
        "/api/v1/auth/request-password-reset",
        json={"email": "unknown@clinic.com"},
    )
    assert response.status_code == 200
    assert "Si el correo existe" in response.json()["message"]


def test_password_reset_rejects_invalid_code(client, monkeypatch) -> None:
    def _send(self, *, recipient: str, full_name: str | None, code: str):
        return SimpleNamespace(
            delivered=True, destination=recipient, subject="reset", artifact_path=None
        )

    monkeypatch.setattr(EmailDeliveryAdapter, "send_password_reset_code", _send)

    register = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Reset Demo",
            "email": "reset2@clinic.com",
            "password": "secret123",
        },
    )
    assert register.status_code == 201

    request_reset = client.post(
        "/api/v1/auth/request-password-reset",
        json={"email": "reset2@clinic.com"},
    )
    assert request_reset.status_code == 200

    reset = client.post(
        "/api/v1/auth/reset-password",
        json={
            "email": "reset2@clinic.com",
            "code": "000000",
            "new_password": "newsecret123",
        },
    )
    assert reset.status_code == 400
    assert "Codigo invalido o expirado" in reset.text
