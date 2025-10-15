"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pytest

from ttsplayer.models import Track


@pytest.fixture
def sample_tracks(tmp_path: Path) -> Iterable[Track]:
    audio_a = tmp_path / "greeting.wav"
    audio_a.write_bytes(b"RIFF\x00\x00\x00\x00WAVEfmt ")
    transcript_a = tmp_path / "greeting.txt"
    transcript_a.write_text("Hello there!", encoding="utf-8")

    audio_b = tmp_path / "farewell.ogg"
    audio_b.write_bytes(b"OggS")

    return [
        Track(
            identifier="greeting.wav",
            title="Greeting",
            audio_path=audio_a,
            transcript_path=transcript_a,
            transcript="Hello there!",
        ),
        Track(
            identifier="farewell.ogg",
            title="Farewell",
            audio_path=audio_b,
            transcript_path=None,
            transcript=None,
        ),
    ]
