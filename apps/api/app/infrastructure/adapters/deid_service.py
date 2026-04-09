"""De-identification adapter with reversible mapping support."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(slots=True)
class MappingRecord:
    entity_type: str
    placeholder: str
    original_value: str


@dataclass(slots=True)
class DeidentificationResult:
    text: str
    mappings: list[MappingRecord]


class DeidentificationService:
    """Simple regex-driven de-identification for MVP."""

    _PATTERNS: dict[str, str] = {
        "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "PHONE": r"\b(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{2,4}\)?[\s-]?)?\d{3,4}[\s-]?\d{3,4}\b",
        "ID": r"\b\d{6,12}\b",
        "ADDRESS": r"\b(?:calle|carrera|avenida|av\.?|cra\.?|cl\.?|street|st\.?|road|rd\.?)\s+[\w\d#\-\s]{3,}\b",
    }

    def deidentify(
        self,
        text: str,
        *,
        known_names: list[str] | None = None,
    ) -> DeidentificationResult:
        mappings: list[MappingRecord] = []
        redacted = text

        for entity_type, pattern in self._PATTERNS.items():
            redacted, replacements = self._replace_by_pattern(redacted, pattern, entity_type)
            mappings.extend(replacements)

        if known_names:
            for name in known_names:
                stripped = name.strip()
                if not stripped:
                    continue
                escaped = re.escape(stripped)
                redacted, replacements = self._replace_by_pattern(
                    redacted,
                    rf"\b{escaped}\b",
                    "NAME",
                    flags=re.IGNORECASE,
                )
                mappings.extend(replacements)

        redacted, third_party = self._replace_by_pattern(
            redacted,
            r"\b(?:mi|su)\s+(?:hijo|hija|madre|padre|hermano|hermana|pareja)\s+([A-Z][a-z]{2,})\b",
            "THIRD_PARTY_NAME",
            capture_group=1,
        )
        mappings.extend(third_party)

        return DeidentificationResult(text=redacted, mappings=mappings)

    def _replace_by_pattern(
        self,
        text: str,
        pattern: str,
        entity_type: str,
        *,
        flags: int = 0,
        capture_group: int | None = None,
    ) -> tuple[str, list[MappingRecord]]:
        counter = 0
        mappings: list[MappingRecord] = []

        def repl(match: re.Match[str]) -> str:
            nonlocal counter
            counter += 1
            original = match.group(capture_group) if capture_group else match.group(0)
            placeholder = f"[{entity_type}_{counter}]"
            mappings.append(
                MappingRecord(entity_type=entity_type.lower(), placeholder=placeholder, original_value=original)
            )
            if capture_group:
                return match.group(0).replace(original, placeholder)
            return placeholder

        updated = re.sub(pattern, repl, text, flags=flags)
        return updated, mappings
