"""Google Workspace events webhook validation helpers."""

from __future__ import annotations

import hashlib
import hmac

from app.core.config import settings


class WorkspaceEventsAdapter:
    """Validate incoming event authenticity for MVP."""

    HEADER_SIGNATURE = "x-google-workspace-signature"

    def validate_signature(self, *, body: bytes, signature_header: str | None) -> bool:
        secret = settings.google_webhook_shared_secret
        if not secret:
            return True
        if not signature_header:
            return False

        expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature_header)