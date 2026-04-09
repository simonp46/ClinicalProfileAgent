"""Prompt template registry."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.models import PromptTemplate


class PromptRegistry:
    """Load prompt templates from DB first, then filesystem fallback."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.prompt_dir = Path(__file__).resolve().parents[3] / "prompts" / settings.prompt_version

    def get_prompt(self, name: str) -> str:
        template = self.db.scalar(
            select(PromptTemplate).where(
                PromptTemplate.name == name,
                PromptTemplate.version == settings.prompt_version,
                PromptTemplate.is_active.is_(True),
            )
        )
        if template:
            return template.content

        path = self.prompt_dir / f"{name}.md"
        if not path.exists():
            raise FileNotFoundError(f"Prompt template not found: {name}")
        return path.read_text(encoding="utf-8")

    def ensure_seeded(self, names: list[str]) -> None:
        for name in names:
            path = self.prompt_dir / f"{name}.md"
            if not path.exists():
                raise FileNotFoundError(f"Prompt template not found: {name}")
            file_content = path.read_text(encoding="utf-8")

            existing = self.db.scalar(
                select(PromptTemplate).where(
                    PromptTemplate.name == name,
                    PromptTemplate.version == settings.prompt_version,
                )
            )
            if existing:
                if existing.content != file_content or not existing.is_active:
                    existing.content = file_content
                    existing.is_active = True
                    self.db.add(existing)
                continue

            self.db.add(
                PromptTemplate(
                    name=name,
                    version=settings.prompt_version,
                    content=file_content,
                    is_active=True,
                )
            )
