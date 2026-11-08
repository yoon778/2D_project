"""Background music on the mixer opened by pico2d's canvas."""
import math
from pathlib import Path

import pico2d.pico2d as p


_OPENING_VOLUME = 32
_EXPLORE_VOLUME = 22
_NEAR_VOLUME = 8
_NEAR_DISTANCE = 120.0
_FAR_DISTANCE = 180.0
_VOLUME_TIME = .25


class BackgroundMusic:
    """Start after canvas initialization and close before canvas teardown."""

    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._music = None
        self._can_start = True
        self._paused = False
        self._volume = float(_OPENING_VOLUME)
        self._applied_volume = _OPENING_VOLUME

    def start(self) -> None:
        if not self._can_start:
            return
        self._can_start = False
        music = None
        try:
            if not self._path.is_file() or p.Mix_QuerySpec(None, None, None) <= 0:
                return
            music = p.Mix_LoadMUS(str(self._path).encode("utf-8"))
            if not music:
                return
            p.Mix_VolumeMusic(self._applied_volume)
            if p.Mix_PlayMusic(music, -1) == 0:
                self._music = music
        except (OSError, RuntimeError):
            pass
        finally:
            if music and self._music is None:
                p.Mix_FreeMusic(music)

    def update(self, dt: float, *, distance: float | None = None, opening: bool = False,
               focused: bool = True) -> None:
        if self._music is None:
            return
        if not focused:
            if not self._paused:
                p.Mix_PauseMusic()
                self._paused = True
            return
        if self._paused:
            p.Mix_ResumeMusic()
            self._paused = False
        if not math.isfinite(dt) or dt <= 0:
            return

        target = _OPENING_VOLUME if opening else _EXPLORE_VOLUME
        if not opening and distance is not None and math.isfinite(distance):
            fraction = (distance - _NEAR_DISTANCE) / (_FAR_DISTANCE - _NEAR_DISTANCE)
            target = _NEAR_VOLUME + (_EXPLORE_VOLUME - _NEAR_VOLUME) * min(1.0, max(0.0, fraction))
        self._volume += (target - self._volume) * -math.expm1(-dt / _VOLUME_TIME)
        volume = round(self._volume)
        if volume != self._applied_volume:
            p.Mix_VolumeMusic(volume)
            self._applied_volume = volume

    def close(self) -> None:
        self._can_start = False
        music, self._music = self._music, None
        if music is not None:
            try:
                p.Mix_HaltMusic()
            finally:
                p.Mix_FreeMusic(music)
