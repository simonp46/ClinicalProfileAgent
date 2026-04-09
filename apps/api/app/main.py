"""FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import audit_logs, auth, documents, drafts, profile, risk_flags, sessions, webhooks
from app.core.config import settings
from app.infrastructure.observability.logging import configure_logging
from app.infrastructure.observability.otel import configure_otel


def create_app() -> FastAPI:
    configure_logging(settings.api_log_level)

    app = FastAPI(
        title="therapy-meet-copilot API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    if settings.otel_exporter_otlp_endpoint is not None or settings.api_env == "development":
        configure_otel(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(webhooks.router)
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(profile.router, prefix="/api/v1")
    app.include_router(sessions.router, prefix="/api/v1")
    app.include_router(drafts.router, prefix="/api/v1")
    app.include_router(documents.router, prefix="/api/v1")
    app.include_router(risk_flags.router, prefix="/api/v1")
    app.include_router(audit_logs.router, prefix="/api/v1")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    def ready() -> dict[str, str]:
        return {"status": "ready"}

    return app


app = create_app()
