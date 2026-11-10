"""Background music and gameplay effects on pico2d's mixer."""
import ctypes
import math
from pathlib import Path

import pico2d.pico2d as p


_OPENING_VOLUME = 32
_EXPLORE_VOLUME = 22
_NEAR_VOLUME = 8
_NEAR_DISTANCE = 120.0
_FAR_DISTANCE = 180.0
_VOLUME_TIME = .25
_HEARING_RANGE = 520.0
_WALL_GAIN = 0.65
_STEP_SPACING = 32.0
_GROAN_DELAY = .4
_GROAN_INTERVAL = 3.2
_ZOMBIE_VOLUME = {"zombie_step": 48, "zombie_groan": 60}
_BOTTLE_SOUND = "bottle_break"


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


class ZombieAudio:
    def __init__(self, directory: Path):
        self._sounds = {}
        self._channels = {}
        self._step_distance = 0.0
        self._groan_in = _GROAN_DELAY
        if p.Mix_QuerySpec(None, None, None) <= 0:
            return
        for kind in (*_ZOMBIE_VOLUME, _BOTTLE_SOUND):
            sound = p.Mix_LoadWAV(str(directory / f"{kind}.wav").encode("utf-8"))
            if sound:
                self._sounds[kind] = sound

    @staticmethod
    def _playing(channel, sound):
        if channel is None or not p.Mix_Playing(channel):
            return False
        # A finished effect's mixer channel may already belong to another sound.
        current = p.Mix_GetChunk(channel)
        return ctypes.cast(current, ctypes.c_void_p).value == ctypes.cast(sound, ctypes.c_void_p).value

    def update(self, dt, *, distance, stride, active, occluded=False):
        if not self._sounds:
            return
        if not active:
            self.stop()
            return
        if distance is None or distance >= _HEARING_RANGE:
            self._stop_zombies()
            return

        self._step_distance += stride
        step_due = self._step_distance >= _STEP_SPACING
        if step_due:
            self._step_distance %= _STEP_SPACING
        self._groan_in -= dt
        groan_due = self._groan_in <= 0
        if groan_due:
            self._groan_in += _GROAN_INTERVAL

        gain = 1.0 - distance / _HEARING_RANGE
        if occluded:
            gain *= _WALL_GAIN
        for kind, due in (("zombie_step", step_due), ("zombie_groan", groan_due)):
            sound = self._sounds.get(kind)
            if sound is None:
                continue
            playing = self._playing(self._channels.get(kind), sound)
            if not playing:
                self._channels.pop(kind, None)
            if playing or due:
                p.Mix_VolumeChunk(sound, max(1, round(_ZOMBIE_VOLUME[kind] * gain)))
            if due and not playing:
                channel = p.Mix_PlayChannelTimed(-1, sound, 0, -1)
                if channel >= 0:
                    self._channels[kind] = channel

    def play_bottle_break(self, distance):
        sound = self._sounds.get(_BOTTLE_SOUND)
        if sound is None or distance >= _HEARING_RANGE:
            return
        self._stop_channel(_BOTTLE_SOUND)
        p.Mix_VolumeChunk(sound, max(1, round(82 * (1.0 - distance / _HEARING_RANGE))))
        channel = p.Mix_PlayChannelTimed(-1, sound, 0, -1)
        if channel >= 0:
            self._channels[_BOTTLE_SOUND] = channel

    def _stop_channel(self, kind):
        channel = self._channels.pop(kind, None)
        if self._playing(channel, self._sounds.get(kind)):
            p.Mix_HaltChannel(channel)

    def _stop_zombies(self):
        for kind in _ZOMBIE_VOLUME:
            self._stop_channel(kind)
        self._step_distance = 0.0
        self._groan_in = _GROAN_DELAY

    def stop(self):
        self._stop_zombies()
        self._stop_channel(_BOTTLE_SOUND)

    def close(self):
        self.stop()
        for sound in self._sounds.values():
            p.Mix_FreeChunk(sound)
        self._sounds.clear()
