"""Playback services built around pygame."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable

import time

import pygame

from ttsplayer.models import Track


class TrackPlayer:
    """Simple wrapper around pygame.mixer with track preloading and quick switching."""

    def __init__(
        self,
        *,
        mixer: pygame.mixer = pygame.mixer,
        num_channels: int = 4,
        time_provider: Callable[[], float] | None = None,
    ) -> None:
        self._mixer = mixer
        if not self._mixer.get_init():
            self._mixer.init()

        self._mixer.set_num_channels(max(self._mixer.get_num_channels(), num_channels))

        init_info = self._mixer.get_init()
        if init_info:
            frequency, format_bits, channels = init_info
            self._sample_rate: int | None = frequency
            bytes_per_sample = max(1, abs(format_bits) // 8)
            self._bytes_per_frame: int | None = bytes_per_sample * max(1, channels)
        else:
            self._sample_rate = None
            self._bytes_per_frame = None

        self._sounds: dict[str, pygame.mixer.Sound] = {}
        self._lengths: dict[str, float] = {}
        self._raw_audio: dict[str, bytes] = {}
        self._current_track: str | None = None
        self._current_channel: pygame.mixer.Channel | None = None
        self._active_segment: pygame.mixer.Sound | None = None
        self._start_timestamp: float | None = None
        self._current_offset: float = 0.0
        self._last_position: float = 0.0
        self._clock: Callable[[], float] = time_provider or time.monotonic

    def preload(self, tracks: Iterable[Track]) -> None:
        """Load sounds into memory for instant playback."""
        for track in tracks:
            if track.identifier in self._sounds:
                continue
            sound = self._load_sound(track.audio_path)
            self._sounds[track.identifier] = sound
            try:
                self._lengths[track.identifier] = float(sound.get_length())
            except (AttributeError, TypeError):
                self._lengths[track.identifier] = 0.0
            try:
                raw = sound.get_raw()  # type: ignore[assignment]
            except (AttributeError, pygame.error):
                raw = None
            if raw:
                self._raw_audio[track.identifier] = raw

    def _load_sound(self, audio_path: Path) -> pygame.mixer.Sound:
        return self._mixer.Sound(audio_path.as_posix())

    def play(self, track_id: str, *, start: float = 0.0) -> None:
        """Play the requested track, restarting immediately if another track is active."""
        if track_id not in self._sounds:
            raise KeyError(f"Track {track_id!r} not preloaded")

        self.stop()
        sound, actual_start, is_partial = self._prepare_sound(track_id, start)
        if sound is None:
            self._current_track = track_id
            self._current_offset = actual_start
            self._last_position = actual_start
            self._start_timestamp = None
            return

        channel = self._mixer.find_channel()
        if channel is None:
            channel = self._mixer.Channel(0)

        channel.play(sound)
        self._current_channel = channel
        self._current_track = track_id
        self._current_offset = max(0.0, actual_start)
        self._last_position = self._current_offset
        self._start_timestamp = self._clock()
        self._active_segment = sound if is_partial else None

    def stop(self) -> None:
        """Stop playback if a track is active."""
        if self._current_channel and self._current_channel.get_busy():
            self._current_channel.stop()
        self._current_channel = None
        self._current_track = None
        self._start_timestamp = None
        self._current_offset = 0.0
        self._last_position = 0.0
        self._active_segment = None

    def is_playing(self) -> bool:
        """Return True if audio is currently playing."""
        return bool(self._current_channel and self._current_channel.get_busy())

    def set_volume(self, volume: float) -> None:
        """Set global volume between 0.0 and 1.0."""
        clamped = max(0.0, min(volume, 1.0))
        if self._current_channel:
            self._current_channel.set_volume(clamped)
        for sound in self._sounds.values():
            sound.set_volume(clamped)

    def get_current_position(self) -> float:
        """Return current playback position in seconds for the active track."""
        if not self._current_track:
            return 0.0

        length = self.get_track_length(self._current_track) or 0.0
        position = self._current_offset

        channel = self._current_channel
        use_clock_fallback = True
        if channel and channel.get_busy():
            try:
                channel_pos_ms = channel.get_pos()
            except AttributeError:
                channel_pos_ms = -1
            if channel_pos_ms and channel_pos_ms >= 0:
                position = self._current_offset + (channel_pos_ms / 1000.0)
                use_clock_fallback = False
        elif channel and not channel.get_busy():
            use_clock_fallback = True

        if use_clock_fallback and self._start_timestamp is not None:
            position = self._current_offset + max(0.0, self._clock() - self._start_timestamp)

        if length:
            position = min(position, length)

        self._last_position = position
        return position

    def seek(self, position: float) -> None:
        """Seek to an offset within the current track."""
        if not self._current_track:
            return
        track_id = self._current_track
        length = self.get_track_length(track_id)
        if length is not None and length > 0:
            position = max(0.0, min(position, length))
        else:
            position = max(0.0, position)

        sound, actual_start, is_partial = self._prepare_sound(track_id, position)
        if sound is None:
            self.stop()
            self._current_track = track_id
            self._current_offset = actual_start
            self._last_position = actual_start
            return

        channel = self._current_channel or self._mixer.find_channel()
        if channel is None:
            channel = self._mixer.Channel(0)

        channel.play(sound)
        self._current_channel = channel
        self._current_offset = actual_start
        self._start_timestamp = self._clock()
        self._last_position = actual_start
        self._current_track = track_id
        self._active_segment = sound if is_partial else None

    def get_track_length(self, track_id: str) -> float | None:
        """Return the known length of a preloaded track, in seconds."""
        return self._lengths.get(track_id)

    def supports_seeking(self, track_id: str) -> bool:
        """Return True if we have raw audio to support seeking for a track."""
        return (
            track_id in self._raw_audio
            and self._sample_rate is not None
            and self._bytes_per_frame is not None
        )

    def _prepare_sound(
        self, track_id: str, start: float
    ) -> tuple[pygame.mixer.Sound | None, float, bool]:
        base_sound = self._sounds[track_id]
        length = self._lengths.get(track_id)

        if start <= 0.0 or not self.supports_seeking(track_id):
            return base_sound, 0.0, False

        raw = self._raw_audio.get(track_id)
        if not raw or not self._sample_rate or not self._bytes_per_frame:
            return base_sound, 0.0, False

        if length is not None and length > 0:
            start = max(0.0, min(start, length))

        offset_frames = int(start * self._sample_rate)
        aligned_offset = offset_frames * self._bytes_per_frame
        if aligned_offset >= len(raw):
            return None, length or start, False

        partial = raw[aligned_offset:]
        try:
            sound = self._mixer.Sound(buffer=partial)
        except (TypeError, pygame.error):
            return base_sound, 0.0, False

        actual_start = aligned_offset / (self._bytes_per_frame * self._sample_rate)
        if length is not None and length > 0:
            actual_start = min(actual_start, length)

        return sound, actual_start, True

    def close(self) -> None:
        """Tear down pygame mixer resources."""
        self.stop()
        self._mixer.quit()
