"""add therapist google oauth fields

Revision ID: 20260407_0006
Revises: 20260330_0005
Create Date: 2026-04-07 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260407_0006"
down_revision = "20260330_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("therapists", sa.Column("google_oauth_subject", sa.String(length=255), nullable=True))
    op.add_column("therapists", sa.Column("google_oauth_access_token", sa.String(length=4096), nullable=True))
    op.add_column("therapists", sa.Column("google_oauth_refresh_token", sa.String(length=4096), nullable=True))
    op.add_column("therapists", sa.Column("google_oauth_scopes", sa.String(length=2048), nullable=True))
    op.add_column("therapists", sa.Column("google_oauth_token_expiry", sa.DateTime(timezone=True), nullable=True))
    op.add_column("therapists", sa.Column("google_oauth_connected_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("therapists", "google_oauth_connected_at")
    op.drop_column("therapists", "google_oauth_token_expiry")
    op.drop_column("therapists", "google_oauth_scopes")
    op.drop_column("therapists", "google_oauth_refresh_token")
    op.drop_column("therapists", "google_oauth_access_token")
    op.drop_column("therapists", "google_oauth_subject")
