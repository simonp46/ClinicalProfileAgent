"""Value objects for transcript processing pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class TranscriptEntry:
    sequence_no: int
    speaker_label: str
    text: str
    original_participant_ref: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None