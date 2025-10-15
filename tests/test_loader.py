from __future__ import annotations

from pathlib import Path

import pytest

from ttsplayer.audio.loader import AudioLibraryLoader


def test_loader_discovers_audio_with_transcripts(tmp_path: Path) -> None:
    (tmp_path / "intro.wav").write_bytes(b"RIFF\x00\x00\x00\x00WAVEfmt ")
    (tmp_path / "intro.txt").write_text("Welcome!", encoding="utf-8")
    (tmp_path / "outro.mp3").write_bytes(b"ID3")

    loader = AudioLibraryLoader(tmp_path)
    tracks = loader.load_tracks()

    assert [track.identifier for track in tracks] == ["intro.wav", "outro.mp3"]
    assert tracks[0].transcript == "Welcome!"
    assert tracks[1].transcript is None


def test_loader_raises_for_missing_directory(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    loader = AudioLibraryLoader(missing)

    with pytest.raises(FileNotFoundError):
        loader.load_tracks()
