"""Transcript normalization utilities."""

from __future__ import annotations

import re
from dataclasses import replace

from app.application.services.transcript_pipeline_types import TranscriptEntry


class TranscriptNormalizer:
    """Normalize transcript entries with stable speaker labels."""

    def normalize_entries(
        self,
        entries: list[TranscriptEntry],
        *,
        therapist_name: str,
        patient_name: str,
    ) -> list[TranscriptEntry]:
        sorted_entries = sorted(
            entries,
            key=lambda item: (
                item.sequence_no,
                item.start_time.isoformat() if item.start_time else "",
            ),
        )
        speaker_map: dict[str, str] = {}
        unknown_counter = 0
        normalized: list[TranscriptEntry] = []

        for entry in sorted_entries:
            label_raw = (entry.speaker_label or "UNKNOWN").strip()
            lower = label_raw.lower()

            if therapist_name and therapist_name.lower() in lower:
                stable_label = "THERAPIST"
            elif patient_name and patient_name.lower() in lower:
                stable_label = "PATIENT"
            elif lower in {"therapist", "terapeuta", "clinician"}:
                stable_label = "THERAPIST"
            elif lower in {"patient", "paciente", "client"}:
                stable_label = "PATIENT"
            else:
                if label_raw not in speaker_map:
                    unknown_counter += 1
                    speaker_map[label_raw] = f"UNKNOWN_SPEAKER_{unknown_counter}"
                stable_label = speaker_map[label_raw]

            text = self._normalize_text(entry.text)
            if not text:
                continue

            normalized.append(
                replace(entry, speaker_label=stable_label, text=text, sequence_no=len(normalized) + 1)
            )

        return self._merge_adjacent(normalized)

    def build_transcript_text(self, entries: list[TranscriptEntry]) -> str:
        return "\n".join(f"[{entry.speaker_label}] {entry.text}" for entry in entries)

    def _normalize_text(self, value: str) -> str:
        value = value.replace("\r", " ").replace("\n", " ")
        value = re.sub(r"\s+", " ", value).strip()
        return value

    def _merge_adjacent(self, entries: list[TranscriptEntry]) -> list[TranscriptEntry]:
        if not entries:
            return []

        merged: list[TranscriptEntry] = [entries[0]]
        for entry in entries[1:]:
            previous = merged[-1]
            if previous.speaker_label == entry.speaker_label:
                merged[-1] = replace(
                    previous,
                    text=f"{previous.text} {entry.text}".strip(),
                    end_time=entry.end_time or previous.end_time,
                )
            else:
                merged.append(entry)

        for idx, item in enumerate(merged, start=1):
            item.sequence_no = idx
        return merged