"""Data structures representing audio tracks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True, frozen=True)
class Track:
    """Represents an audio track and its optional transcript."""

    identifier: str
    title: str
    audio_path: Path
    transcript_path: Path | None = None
    transcript: str | None = None

    def has_transcript(self) -> bool:
        """Return True when transcript metadata is available."""
        return self.transcript is not None
