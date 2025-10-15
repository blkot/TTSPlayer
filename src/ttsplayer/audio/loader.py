"""Track discovery and metadata loading."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from ttsplayer.models import Track


class AudioLibraryLoader:
    """Discover audio assets and their transcripts under a folder."""

    SUPPORTED_EXTENSIONS = (".wav", ".mp3", ".ogg")

    def __init__(self, root: Path | str, *, recursive: bool = False) -> None:
        self.root = Path(root)
        self.recursive = recursive

    def _iter_audio_files(self) -> Iterable[Path]:
        if not self.root.exists():
            raise FileNotFoundError(f"Audio library folder not found: {self.root}")

        pattern = "**/*" if self.recursive else "*"
        for candidate in self.root.glob(pattern):
            if candidate.is_file() and candidate.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                yield candidate

    def load_tracks(self) -> list[Track]:
        """Return a sorted list of discovered audio tracks with transcripts."""
        audio_files = sorted(self._iter_audio_files(), key=lambda path: path.name.lower())
        tracks: list[Track] = []

        for audio_path in audio_files:
            transcript_path = audio_path.with_suffix(".txt")
            transcript = None
            if transcript_path.exists():
                transcript = transcript_path.read_text(encoding="utf-8").strip() or None

            identifier = str(audio_path.relative_to(self.root))
            tracks.append(
                Track(
                    identifier=identifier,
                    title=audio_path.stem.replace("_", " ").title(),
                    audio_path=audio_path,
                    transcript_path=transcript_path if transcript_path.exists() else None,
                    transcript=transcript,
                )
            )

        return tracks
