from __future__ import annotations
from collections.abc import Iterable

import math

import pytest

from ttsplayer.audio.player import TrackPlayer
from ttsplayer.models import Track


SAMPLE_RATE = 22_050
BYTES_PER_FRAME = 2  # simulate mono, 16-bit samples


class FakeSound:
    def __init__(self, identifier: str, length: float, raw: bytes) -> None:
        self.identifier = identifier
        self.volume = 1.0
        self._length = length
        self._raw = raw

    def set_volume(self, volume: float) -> None:
        self.volume = volume

    def get_length(self) -> float:
        return self._length

    def get_raw(self) -> bytes:
        return self._raw


class FakeChannel:
    def __init__(self, mixer: "FakeMixer") -> None:
        self._mixer = mixer
        self._busy = False
        self.volume = 1.0
        self.played: list[FakeSound] = []
        self._start_time_ms: float = 0.0
        self.current_sound: FakeSound | None = None

    def play(self, sound: FakeSound, loops: int = 0, maxtime: int = 0, fade_ms: int = 0) -> None:  # noqa: D401
        self._busy = True
        self.current_sound = sound
        self.played.append(sound)
        self._start_time_ms = self._mixer.current_time_ms

    def stop(self) -> None:
        self._busy = False
        self.current_sound = None

    def get_busy(self) -> bool:
        if not self._busy or not self.current_sound:
            return False
        elapsed = max(0.0, (self._mixer.current_time_ms - self._start_time_ms) / 1000.0)
        playing = elapsed < self.current_sound.get_length()
        if not playing:
            self._busy = False
            self.current_sound = None
        return playing

    def get_pos(self) -> int:
        if not self._busy or not self.current_sound:
            return 0
        elapsed = max(0.0, self._mixer.current_time_ms - self._start_time_ms)
        return int(elapsed)

    def set_volume(self, volume: float) -> None:
        self.volume = volume


class FakeMixer:
    def __init__(self) -> None:
        self._init = False
        self.channels = [FakeChannel(self)]
        self.sounds: list[FakeSound] = []
        self.length_map: dict[str, float] = {}
        self.current_time_ms: float = 0.0

    def get_init(self):
        if not self._init:
            return None
        return SAMPLE_RATE, -16, 1

    def init(self) -> None:
        self._init = True

    def get_num_channels(self) -> int:
        return len(self.channels)

    def set_num_channels(self, count: int) -> None:
        while len(self.channels) < count:
            self.channels.append(FakeChannel(self))

    def Sound(self, *args, **kwargs) -> FakeSound:  # noqa: N802 - mirrors pygame API
        if "buffer" in kwargs:
            raw_arg = kwargs["buffer"]
            raw = bytes(raw_arg)
            length = len(raw) / (BYTES_PER_FRAME * SAMPLE_RATE)
            sound = FakeSound("<buffer>", length, raw)
        else:
            path = args[0]
            length = self.length_map.get(path, 1.0)
            frame_count = int(length * SAMPLE_RATE)
            raw = b"x" * max(1, frame_count * BYTES_PER_FRAME)
            sound = FakeSound(path, length, raw)
        self.sounds.append(sound)
        return sound

    def find_channel(self) -> FakeChannel | None:
        return self.channels[0]

    def Channel(self, index: int) -> FakeChannel:  # noqa: N802 - mirrors pygame API
        return self.channels[index]

    def quit(self) -> None:
        self._init = False

    def tick(self, milliseconds: float) -> None:
        self.current_time_ms += milliseconds

    def reset(self) -> None:
        self.current_time_ms = 0.0


def make_player(lengths: dict[str, float]) -> tuple[TrackPlayer, FakeMixer]:
    mixer = FakeMixer()
    mixer.length_map = lengths
    clock = lambda: mixer.current_time_ms / 1000.0
    player = TrackPlayer(mixer=mixer, time_provider=clock)
    return player, mixer


def test_player_preload_and_play(sample_tracks: Iterable[Track]) -> None:
    lengths = {track.audio_path.as_posix(): 3.0 for track in sample_tracks}
    player, mixer = make_player(lengths)

    player.preload(sample_tracks)
    assert len(mixer.sounds) == 2
    assert player.supports_seeking("greeting.wav") is True

    player.play("greeting.wav")
    assert mixer.channels[0].get_busy() is True
    assert player.is_playing() is True

    player.stop()
    assert player.is_playing() is False


def test_player_volume_controls(sample_tracks: Iterable[Track]) -> None:
    player, mixer = make_player({})
    player.preload(sample_tracks)
    player.play("greeting.wav")

    player.set_volume(0.25)

    assert all(abs(sound.volume - 0.25) < 1e-6 for sound in mixer.sounds)
    assert abs(mixer.channels[0].volume - 0.25) < 1e-6


def test_player_requires_preloaded_track(sample_tracks: Iterable[Track]) -> None:
    player, _ = make_player({})
    player.preload(sample_tracks)

    with pytest.raises(KeyError):
        player.play("unknown")


def test_player_reports_position_and_length(sample_tracks: Iterable[Track]) -> None:
    lengths = {track.audio_path.as_posix(): 4.0 for track in sample_tracks}
    player, mixer = make_player(lengths)
    player.preload(sample_tracks)

    player.play("greeting.wav")
    mixer.tick(1500)
    assert math.isclose(player.get_current_position(), 1.5, rel_tol=1e-3)
    assert math.isclose(player.get_track_length("greeting.wav") or 0.0, 4.0, rel_tol=1e-3)


def test_player_seek_updates_position(sample_tracks: Iterable[Track]) -> None:
    lengths = {track.audio_path.as_posix(): 5.0 for track in sample_tracks}
    player, mixer = make_player(lengths)
    player.preload(sample_tracks)
    player.play("greeting.wav")

    player.seek(2.5)
    assert math.isclose(player.get_current_position(), 2.5, rel_tol=1e-3)
    current_sound = mixer.channels[0].current_sound
    assert current_sound is not None
    remaining = current_sound.get_length()
    assert math.isclose(remaining, 5.0 - 2.5, rel_tol=1e-2)


def test_player_seek_past_end_stops(sample_tracks: Iterable[Track]) -> None:
    lengths = {track.audio_path.as_posix(): 3.0 for track in sample_tracks}
    player, _ = make_player(lengths)
    player.preload(sample_tracks)
    player.play("greeting.wav")

    player.seek(10.0)
    assert player.is_playing() is False
    assert math.isclose(player.get_current_position(), 3.0, rel_tol=1e-3)
