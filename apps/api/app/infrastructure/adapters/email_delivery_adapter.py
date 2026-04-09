"""Email delivery adapter for transactional notifications."""

from __future__ import annotations

import json
import smtplib
import ssl
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path

from app.core.config import settings


@dataclass(slots=True)
class EmailDeliveryResult:
    delivered: bool
    destination: str
    subject: str
    artifact_path: str | None = None


class EmailDeliveryAdapter:
    def send_password_reset_code(
        self, *, recipient: str, full_name: str | None, code: str
    ) -> EmailDeliveryResult:
        subject = "Codigo para restablecer tu contrasena"
        greeting = full_name.strip() if full_name else "profesional"
        body = (
            f"Hola {greeting},\n\n"
            f"Tu codigo de verificacion para restablecer la contrasena es: {code}\n\n"
            f"Este codigo expira en {settings.password_reset_code_expire_minutes} minutos. "
            "Si no solicitaste este cambio, puedes ignorar este correo.\n"
        )

        if settings.use_mock_email or not settings.smtp_host:
            artifact_path = self._write_mock_email(
                recipient=recipient, subject=subject, body=body, code=code
            )
            return EmailDeliveryResult(
                delivered=True,
                destination=recipient,
                subject=subject,
                artifact_path=artifact_path,
            )

        message = EmailMessage()
        from_email = settings.smtp_from_email or settings.smtp_username or "noreply@example.com"
        message["From"] = f"{settings.smtp_from_name} <{from_email}>"
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)

        if settings.smtp_use_ssl:
            with smtplib.SMTP_SSL(
                settings.smtp_host,
                settings.smtp_port,
                context=ssl.create_default_context(),
                timeout=20,
            ) as server:
                self._authenticate(server)
                server.send_message(message)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
                if settings.smtp_use_tls:
                    server.starttls(context=ssl.create_default_context())
                self._authenticate(server)
                server.send_message(message)

        return EmailDeliveryResult(delivered=True, destination=recipient, subject=subject)

    def _authenticate(self, server: smtplib.SMTP) -> None:
        if settings.smtp_username and settings.smtp_password:
            server.login(settings.smtp_username, settings.smtp_password)

    def _write_mock_email(self, *, recipient: str, subject: str, body: str, code: str) -> str:
        target_dir = Path(settings.artifacts_dir) / "mock_emails"
        target_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        target = target_dir / f"password-reset-{timestamp}.json"
        target.write_text(
            json.dumps(
                {
                    "recipient": recipient,
                    "subject": subject,
                    "body": body,
                    "code": code,
                },
                ensure_ascii=True,
                indent=2,
            ),
            encoding="utf-8",
        )
        return str(target)
