"""Background music and gameplay effects on pico2d's mixer."""
import ctypes
from dataclasses import dataclass
import math
from pathlib import Path

import pico2d.pico2d as p


_OPENING_VOLUME = 32
_EXPLORE_VOLUME = 38
_NEAR_VOLUME = 16
_CHASE_VOLUME = 10
_NEAR_DISTANCE = 120.0
_FAR_DISTANCE = 180.0
_VOLUME_TIME = .25
_HEARING_RANGE = 520.0
_WALL_GAIN = 0.65
_PAN_FAR_GAIN = 80
_STEP_SPACING = 32.0
_GROAN_DELAY = .4
_GROAN_INTERVAL = 3.2
_ZOMBIE_VOLUME = {"zombie_step": 48, "zombie_groan": 60}
_HEAVY_STEP_SOUND = "zombie_step_heavy"
_HEAVY_STEP_SPACING = 36.0
_HEAVY_STEP_VOLUME = 76
_PATROL_STEP_RANGE = 260.0
_PATROL_STEP_VOLUME = 88
_BOTTLE_SOUND = "bottle_break"
_BOTTLE_THROW_SOUND = "bottle_throw"
_GATE_SOUND = "gate_open"
_VEHICLE_SOUND = "vehicle_alarm"
_VEHICLE_HIT_SOUND = "vehicle_hit"
_BAT_SWING_SOUND = "bat_swing"
_ZOMBIE_HIT_SOUND = "zombie_hit"
_HEAVY_ZOMBIE_HIT_SOUND = "zombie_hit_heavy"
_PLAYER_HIT_SOUND = "player_hit"
_DELIVERY_CUE_SOUND = "cutscene-delivered"
_PARCEL_PICKUP_SOUND = "parcel_pickup"
_PARCEL_DROP_SOUND = "parcel_drop"
_BOTTLE_PICKUP_SOUND = "bottle_pickup"
_MAP_SOUND = "map_rustle"
_PLAYER_STEP_SPACING = {"player_walk": 32.0, "player_run": 48.0, "player_sneak": 32.0}
_EFFECT_VOLUME = {
    _BOTTLE_SOUND: 82,
    _BOTTLE_THROW_SOUND: 48,
    _GATE_SOUND: 72,
    _VEHICLE_SOUND: 76,
    _VEHICLE_HIT_SOUND: 65,
    _BAT_SWING_SOUND: 74,
    _ZOMBIE_HIT_SOUND: 82,
    _HEAVY_ZOMBIE_HIT_SOUND: 88,
    "player_walk": 42,
    "player_run": 67,
    "player_sneak": 20,
    _PLAYER_HIT_SOUND: 78,
    _DELIVERY_CUE_SOUND: 74,
    _PARCEL_PICKUP_SOUND: 40,
    _PARCEL_DROP_SOUND: 46,
    _BOTTLE_PICKUP_SOUND: 35,
    _MAP_SOUND: 33,
}


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
               focused: bool = True, chasing: bool = False) -> None:
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

        if opening:
            target = _OPENING_VOLUME
        elif chasing:
            target = _CHASE_VOLUME
        elif distance is not None and math.isfinite(distance):
            fraction = (distance - _NEAR_DISTANCE) / (_FAR_DISTANCE - _NEAR_DISTANCE)
            target = _NEAR_VOLUME + (_EXPLORE_VOLUME - _NEAR_VOLUME) * min(1.0, max(0.0, fraction))
        else:
            target = _EXPLORE_VOLUME
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


@dataclass(frozen=True)
class PatrolFootstep:
    distance: float
    stride: float
    pan: float
    occluded: bool

    @property
    def volume(self):
        gain = max(0.0, 1.0 - self.distance / _PATROL_STEP_RANGE) ** 1.5
        return _PATROL_STEP_VOLUME * gain * (0.8 if self.occluded else 1.0)


@dataclass(frozen=True)
class HeavyFootstep:
    distance: float
    stride: float
    pan: float
    occluded: bool


def _zombie_gain(distance, occluded):
    return (1.0 - distance / _HEARING_RANGE) * (_WALL_GAIN if occluded else 1.0)


class ZombieAudio:
    def __init__(self, directory: Path):
        self._sounds = {}
        self._channels = {}
        self._step_distance = 0.0
        self._heavy_step_distance = 0.0
        self._patrol_steps = False
        self._player_step_phase = 0.0
        self._groan_in = _GROAN_DELAY
        if p.Mix_QuerySpec(None, None, None) <= 0:
            return
        for kind in (*_ZOMBIE_VOLUME, _HEAVY_STEP_SOUND, *_EFFECT_VOLUME):
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

    def update(self, dt, *, distance, stride, active, occluded=False, preserve_map_cue=False, pan=0.0,
               patrol_step=None, heavy_step=None):
        if not self._sounds:
            return
        if not active:
            self._stop_effects(preserve_map_cue)
            return
        self._update_heavy_step(heavy_step)
        if distance is None or distance >= _HEARING_RANGE:
            self._stop_regular_zombies()
            return

        patrol_steps = patrol_step is not None
        if self._patrol_steps != patrol_steps:
            self._stop_channel("zombie_step")
            self._step_distance = 0.0
            self._patrol_steps = patrol_steps
        self._step_distance += patrol_step.stride if patrol_steps else stride
        step_due = self._step_distance >= _STEP_SPACING
        if step_due:
            self._step_distance %= _STEP_SPACING
        self._groan_in -= dt
        groan_due = self._groan_in <= 0
        if groan_due:
            self._groan_in += _GROAN_INTERVAL

        gain = _zombie_gain(distance, occluded)
        step_volume = patrol_step.volume if patrol_steps else _ZOMBIE_VOLUME["zombie_step"] * gain
        step_pan = patrol_step.pan if patrol_steps else pan
        for kind, due, volume, side in (("zombie_step", step_due, step_volume, step_pan),
                                         ("zombie_groan", groan_due, _ZOMBIE_VOLUME["zombie_groan"] * gain, pan)):
            self._update_zombie_sound(kind, due, volume, side)

    def _update_heavy_step(self, footstep):
        if footstep is None or footstep.distance >= _HEARING_RANGE:
            self._stop_heavy_step()
            return
        self._heavy_step_distance += footstep.stride
        due = self._heavy_step_distance >= _HEAVY_STEP_SPACING
        if due:
            self._heavy_step_distance %= _HEAVY_STEP_SPACING
        volume = _HEAVY_STEP_VOLUME * _zombie_gain(footstep.distance, footstep.occluded)
        self._update_zombie_sound(_HEAVY_STEP_SOUND, due, volume, footstep.pan)

    def _update_zombie_sound(self, kind, due, volume, pan):
        sound = self._sounds.get(kind)
        if sound is None:
            return
        playing = self._playing(self._channels.get(kind), sound)
        if not playing:
            self._channels.pop(kind, None)
        if playing or due:
            p.Mix_VolumeChunk(sound, max(1, round(volume)))
        if due and not playing:
            # Keep each sound on its starting side until its channel ends.
            self._start_channel(kind, sound, pan)

    def play_bottle_break(self, distance, *, pan=0.0):
        self._play_effect(_BOTTLE_SOUND, distance, pan=pan)

    def play_bottle_throw(self):
        self._play_effect(_BOTTLE_THROW_SOUND, 0.0)

    def play_gate_open(self, distance, *, pan=0.0):
        self._play_effect(_GATE_SOUND, distance, pan=pan)

    def play_vehicle_alarm(self, distance, *, pan=0.0):
        self._play_effect(_VEHICLE_SOUND, distance, pan=pan)

    def play_vehicle_hit(self, distance, *, pan=0.0):
        self._play_effect(_VEHICLE_HIT_SOUND, distance, pan=pan)

    def play_bat_swing(self):
        self._play_effect(_BAT_SWING_SOUND, 0.0)

    def play_zombie_hit(self, *, heavy=False):
        kind = _HEAVY_ZOMBIE_HIT_SOUND if heavy and _HEAVY_ZOMBIE_HIT_SOUND in self._sounds else _ZOMBIE_HIT_SOUND
        self._play_effect(kind, 0.0)

    def update_player_steps(self, distance, *, sprinting, sneaking):
        if not math.isfinite(distance) or distance <= 0:
            return
        kind = "player_sneak" if sneaking else "player_run" if sprinting else "player_walk"
        # A half step remains a half step when the player's gait changes.
        self._player_step_phase += distance / _PLAYER_STEP_SPACING[kind]
        completed = math.floor(self._player_step_phase + 1e-12)
        if completed:
            self._player_step_phase = max(0.0, self._player_step_phase - completed)
            self._play_effect(kind, 0.0)

    def play_player_hit(self):
        self._play_effect(_PLAYER_HIT_SOUND, 0.0)

    def play_delivery_cue(self):
        self._play_effect(_DELIVERY_CUE_SOUND, 0.0)

    def play_parcel_pickup(self):
        self._play_effect(_PARCEL_PICKUP_SOUND, 0.0)

    def play_parcel_drop(self):
        self._play_effect(_PARCEL_DROP_SOUND, 0.0)

    def play_bottle_pickup(self):
        self._play_effect(_BOTTLE_PICKUP_SOUND, 0.0)

    def play_map_toggle(self):
        self._play_effect(_MAP_SOUND, 0.0)

    def _play_effect(self, kind, distance, *, pan=0.0):
        sound = self._sounds.get(kind)
        if sound is None or distance >= _HEARING_RANGE:
            return
        self._stop_channel(kind)
        gain = 1.0 - distance / _HEARING_RANGE
        p.Mix_VolumeChunk(sound, max(1, round(_EFFECT_VOLUME[kind] * gain)))
        self._start_channel(kind, sound, pan)

    def _start_channel(self, kind, sound, pan):
        channel = p.Mix_PlayChannelTimed(-1, sound, 0, -1)
        if channel >= 0:
            pan = max(-1.0, min(1.0, pan)) if math.isfinite(pan) else 0.0
            far = round(255 - (255 - _PAN_FAR_GAIN) * abs(pan))
            left, right = (far, 255) if pan > 0 else (255, far)
            # Centered effects also clear any panning on a reused mixer channel.
            p.Mix_SetPanning(channel, left, right)
            self._channels[kind] = channel

    def _stop_channel(self, kind):
        channel = self._channels.pop(kind, None)
        if self._playing(channel, self._sounds.get(kind)):
            p.Mix_HaltChannel(channel)

    def _stop_regular_zombies(self):
        for kind in _ZOMBIE_VOLUME:
            self._stop_channel(kind)
        self._step_distance = 0.0
        self._patrol_steps = False
        self._groan_in = _GROAN_DELAY

    def _stop_heavy_step(self):
        self._stop_channel(_HEAVY_STEP_SOUND)
        self._heavy_step_distance = 0.0

    def _stop_effects(self, preserve_map_cue):
        self._stop_regular_zombies()
        self._stop_heavy_step()
        self._player_step_phase = 0.0
        for kind in _EFFECT_VOLUME:
            if not (preserve_map_cue and kind == _MAP_SOUND):
                self._stop_channel(kind)

    def stop(self):
        self._stop_effects(False)

    def close(self):
        self.stop()
        for sound in self._sounds.values():
            p.Mix_FreeChunk(sound)
        self._sounds.clear()
