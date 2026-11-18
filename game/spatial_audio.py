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
_SCORE_EXPLORE = 30
_SCORE_APPROACH_DISTANCE = 190.0
_SCORE_CLOSE_DISTANCE = 85.0
_SCORE_RISE_TIME = .28
_SCORE_RELEASE_TIME = 1.35
_SCORE_RELIEF_TIME = 1.70
_MIX_MAX_VOLUME = 128
_HEARING_RANGE = 520.0
_WALL_GAIN = 0.65
_PAN_FAR_GAIN = 80
_STEP_SPACING = 32.0
_STEP_IDLE_GRACE = .30
_GROAN_DELAY = .4
_GROAN_INTERVAL = 3.2
_HEAVY_GROAN_SOUND = "zombie_groan_heavy"
_ZOMBIE_VOLUME = {"zombie_step": 48, "zombie_groan": 60, _HEAVY_GROAN_SOUND: 60}
_HEAVY_STEP_SOUND = "zombie_step_heavy"
_HEAVY_STEP_SPACING = 36.0
_HEAVY_STEP_VOLUME = 76
_PATROL_STEP_RANGE = 260.0
_PATROL_STEP_VOLUME = 88
_BOTTLE_SOUND = "bottle_break"
_BOTTLE_THROW_SOUND = "bottle_throw"
_GATE_SOUND = "gate_open"
_SHUTTER_SOUND = "shutter_close"
_BRIDGE_MOTOR_SOUND = "bridge_motor"
_BUS_BROADCAST_SOUND = "bus_broadcast"
_TRUCK_CUES = {
    "arriving": "truck_arrive",
    "parking": "truck_stop",
    "disembarking": "truck_cab",
    "unloading": "truck_cargo",
    "boarding": "truck_cab",
    "departing": "truck_depart",
}
_TRUCK_SOUNDS = frozenset(_TRUCK_CUES.values())
_VEHICLE_SOUND = "vehicle_alarm"
_VEHICLE_HIT_SOUND = "vehicle_hit"
_BAT_SWING_SOUND = "bat_swing"
_BAT_BREAK_SOUND = "bat_break"
_FIST_HIT_SOUND = "fist_hit"
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
    _SHUTTER_SOUND: 72,
    _BRIDGE_MOTOR_SOUND: 86,
    _BUS_BROADCAST_SOUND: 92,
    "truck_arrive": 78,
    "truck_stop": 78,
    "truck_cab": 79,
    "truck_cargo": 74,
    "truck_depart": 81,
    _VEHICLE_SOUND: 76,
    _VEHICLE_HIT_SOUND: 65,
    _BAT_SWING_SOUND: 74,
    _BAT_BREAK_SOUND: 63,
    _FIST_HIT_SOUND: 66,
    _ZOMBIE_HIT_SOUND: 82,
    _HEAVY_ZOMBIE_HIT_SOUND: 88,
    "player_walk": 34,
    "player_run": 50,
    "player_sneak": 16,
    _PLAYER_HIT_SOUND: 78,
    _DELIVERY_CUE_SOUND: 74,
    _PARCEL_PICKUP_SOUND: 40,
    _PARCEL_DROP_SOUND: 46,
    _BOTTLE_PICKUP_SOUND: 35,
    _MAP_SOUND: 33,
}


@dataclass
class AudioSettings:
    master: int = 100
    music: int = 100
    effects: int = 100

    def music_volume(self, volume):
        return round(volume * self.master * self.music / 10000)

    def effect_volume(self, volume):
        return round(volume * self.master * self.effects / 10000)


def _unit(value):
    return max(0.0, min(1.0, value)) if value is not None and math.isfinite(value) else 0.0


def _relief_gain(elapsed):
    return (1.0 - elapsed / _SCORE_RELIEF_TIME) ** 1.4


def _advance_relief(elapsed, dt, relief):
    return max(0.0, min(_SCORE_RELIEF_TIME, elapsed + dt if relief else elapsed - dt))


class BackgroundMusic:
    """Start after canvas initialization and close before canvas teardown."""

    def __init__(self, path: str | Path, *, layers=(), settings: AudioSettings | None = None):
        self._path = Path(path)
        self._settings = settings if settings is not None else AudioSettings()
        self._score = _AdaptiveScore((self._path, *map(Path, layers)), self._settings) if layers else None
        self._music = None
        self._can_start = True
        self._paused = False
        self._volume = float(_OPENING_VOLUME)
        self._applied_volume = _OPENING_VOLUME
        self._relief_elapsed = 0.0

    def start(self) -> None:
        if not self._can_start:
            return
        self._can_start = False
        if self._score is not None:
            if self._score.start():
                return
            self._score = None
        music = None
        try:
            if not self._path.is_file() or p.Mix_QuerySpec(None, None, None) <= 0:
                return
            music = p.Mix_LoadMUS(str(self._path).encode("utf-8"))
            if not music:
                return
            self._applied_volume = self._settings.music_volume(round(self._volume))
            p.Mix_VolumeMusic(self._applied_volume)
            if p.Mix_PlayMusic(music, -1) == 0:
                self._music = music
        except (OSError, RuntimeError):
            pass
        finally:
            if music and self._music is None:
                p.Mix_FreeMusic(music)

    def update(self, dt: float, *, distance: float | None = None, opening: bool = False,
               focused: bool = True, chasing: bool = False, threat: float | None = None,
               combat: float | None = None, relief: bool = False) -> None:
        if self._score is not None:
            self._score.update(dt, distance=distance, focused=focused, chasing=chasing,
                               threat=threat, combat=combat, relief=relief)
            return
        if self._music is None:
            return
        if not focused:
            if not self._paused:
                p.Mix_PauseMusic()
                self._paused = True
            self._apply_volume()
            return
        if self._paused:
            p.Mix_ResumeMusic()
            self._paused = False
        if not math.isfinite(dt) or dt <= 0:
            self._apply_volume()
            return

        self._relief_elapsed = _advance_relief(self._relief_elapsed, dt, relief)
        if opening:
            target = _OPENING_VOLUME
        elif threat is not None or combat is not None:
            near = _EXPLORE_VOLUME + (_NEAR_VOLUME - _EXPLORE_VOLUME) * _unit(threat)
            target = near + (_CHASE_VOLUME - near) * _unit(combat if combat is not None else chasing)
        elif chasing:
            target = _CHASE_VOLUME
        elif distance is not None and math.isfinite(distance):
            fraction = (distance - _NEAR_DISTANCE) / (_FAR_DISTANCE - _NEAR_DISTANCE)
            target = _NEAR_VOLUME + (_EXPLORE_VOLUME - _NEAR_VOLUME) * min(1.0, max(0.0, fraction))
        else:
            target = _EXPLORE_VOLUME
        self._volume += (target - self._volume) * -math.expm1(-dt / _VOLUME_TIME)
        self._apply_volume()

    def _apply_volume(self):
        volume = self._settings.music_volume(round(self._volume * _relief_gain(self._relief_elapsed)))
        if volume != self._applied_volume:
            p.Mix_VolumeMusic(volume)
            self._applied_volume = volume

    def reset(self) -> None:
        self._relief_elapsed = 0.0
        if self._score is not None:
            self._score.reset()

    def close(self) -> None:
        self._can_start = False
        if self._score is not None:
            self._score.close()
            self._score = None
        music, self._music = self._music, None
        if music is not None:
            try:
                p.Mix_HaltMusic()
            finally:
                p.Mix_FreeMusic(music)


class _AdaptiveScore:
    """Three equal-length loops on reserved channels, mixed without restarting."""

    def __init__(self, paths, settings):
        self._paths = paths
        self._settings = settings
        self._chunks = []
        self._started = 0
        self._original_channels = None
        self._original_volumes = ()
        self._paused = False
        self._pressure = 0.0
        self._pursuit = 0.0
        self._relief_elapsed = 0.0
        self._volumes = (_SCORE_EXPLORE, 0, 0)

    def start(self):
        if not all(path.is_file() for path in self._paths) or p.Mix_QuerySpec(None, None, None) <= 0:
            return False
        try:
            for path in self._paths:
                chunk = p.Mix_LoadWAV(str(path).encode("utf-8"))
                if not chunk:
                    return False
                self._chunks.append(chunk)
            if len({chunk.contents.alen for chunk in self._chunks}) != 1:
                return False
            self._original_channels = p.Mix_AllocateChannels(-1)
            count = len(self._chunks)
            if (p.Mix_AllocateChannels(self._original_channels + count) != self._original_channels + count
                    or p.Mix_ReserveChannels(count) != count):
                return False
            self._original_volumes = tuple(p.Mix_Volume(channel, -1) for channel in range(count))
            self._volumes = (self._settings.music_volume(_SCORE_EXPLORE), 0, 0)
            for channel, (chunk, volume) in enumerate(zip(self._chunks, self._volumes)):
                p.Mix_Volume(channel, volume)
                if p.Mix_PlayChannelTimed(channel, chunk, -1, -1) != channel:
                    return False
                self._started += 1
            return True
        finally:
            if self._started != len(self._paths):
                self.close()

    def update(self, dt, *, distance, focused, chasing, threat, combat, relief):
        if not self._started:
            return
        paused = not focused
        if self._paused != paused:
            switch = p.Mix_Resume if focused else p.Mix_Pause
            for channel in range(self._started):
                switch(channel)
            self._paused = paused
        if focused and math.isfinite(dt) and dt > 0:
            distance = distance if distance is not None and math.isfinite(distance) else _SCORE_APPROACH_DISTANCE
            proximity = (_SCORE_APPROACH_DISTANCE - distance) / (_SCORE_APPROACH_DISTANCE - _SCORE_CLOSE_DISTANCE)
            pursuit = _unit(combat if combat is not None else chasing)
            target = max(pursuit, _unit(proximity if threat is None else threat))
            if relief:
                target = pursuit = 0.0
            self._pressure = self._fade(self._pressure, target, dt)
            self._pursuit = self._fade(self._pursuit, pursuit, dt)
            self._relief_elapsed = _advance_relief(self._relief_elapsed, dt, relief)
        gain = _relief_gain(self._relief_elapsed)
        self._set_volumes(tuple(round(value * gain) for value in (
            _SCORE_EXPLORE - 10 * self._pressure - 4 * self._pursuit,
            24 * self._pressure - 10 * self._pursuit,
            38 * self._pursuit,
        )))

    def reset(self):
        self._pressure = self._pursuit = self._relief_elapsed = 0.0
        if self._started:
            self._set_volumes((_SCORE_EXPLORE, 0, 0))

    def _set_volumes(self, volumes):
        volumes = tuple(self._settings.music_volume(volume) for volume in volumes)
        for channel, (previous, volume) in enumerate(zip(self._volumes, volumes)):
            if previous != volume:
                p.Mix_Volume(channel, volume)
        self._volumes = volumes

    @staticmethod
    def _fade(current, target, dt):
        duration = _SCORE_RISE_TIME if target > current else _SCORE_RELEASE_TIME
        return current + (target - current) * -math.expm1(-dt / duration)

    def close(self):
        for channel in range(self._started):
            p.Mix_HaltChannel(channel)
        self._started = 0
        for chunk in self._chunks:
            p.Mix_FreeChunk(chunk)
        self._chunks.clear()
        if self._original_channels is not None:
            for channel, volume in enumerate(self._original_volumes):
                p.Mix_Volume(channel, volume)
            self._original_volumes = ()
            p.Mix_ReserveChannels(0)
            p.Mix_AllocateChannels(self._original_channels)
            self._original_channels = None


@dataclass(frozen=True)
class PatrolFootstep:
    distance: float
    stride: float
    pan: float
    occluded: bool

    @property
    def volume(self):
        return _patrol_volume(self.distance, self.occluded)


@dataclass(frozen=True)
class HeavyFootstep:
    distance: float
    stride: float
    pan: float
    occluded: bool


@dataclass(frozen=True)
class ZombieFootstep:
    source_id: int
    distance: float
    stride: float
    pan: float
    occluded: bool = False
    kind: str = "regular"


@dataclass
class _FootstepProgress:
    distance: float = 0.0
    idle: float = 0.0


def _patrol_volume(distance, occluded):
    gain = max(0.0, 1.0 - distance / _PATROL_STEP_RANGE) ** 1.5
    return _PATROL_STEP_VOLUME * gain * (0.8 if occluded else 1.0)


def _zombie_gain(distance, occluded):
    return (1.0 - distance / _HEARING_RANGE) * (_WALL_GAIN if occluded else 1.0)


class ZombieAudio:
    def __init__(self, directory: Path, *, settings: AudioSettings | None = None):
        self._settings = settings if settings is not None else AudioSettings()
        self._sounds = {}
        self._channels = {}
        self._step_distance = 0.0
        self._heavy_step_distance = 0.0
        self._patrol_steps = False
        self._directional_mode = False
        self._footstep_progress = {}
        self._footstep_tails = {}
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
               patrol_step=None, heavy_step=None, preserve_truck_cues=False, footstep_sources=None,
               heavy_groan=False):
        if not self._sounds:
            return
        if not active:
            self._stop_effects(preserve_map_cue, preserve_truck_cues=preserve_truck_cues)
            return
        directional = footstep_sources is not None
        if directional != self._directional_mode:
            self._switch_footstep_mode(directional)
        if directional:
            self._update_directional_steps(dt, footstep_sources)
        else:
            self._update_heavy_step(heavy_step)
        if distance is None or distance >= _HEARING_RANGE:
            self._stop_regular_zombies()
            return

        if not directional:
            self._update_regular_step(distance, occluded, stride, pan, patrol_step)
        self._groan_in -= dt
        groan_due = self._groan_in <= 0
        if groan_due:
            self._groan_in += _GROAN_INTERVAL
        groan = _HEAVY_GROAN_SOUND if heavy_groan else "zombie_groan"
        self._update_zombie_sound(groan, groan_due, _ZOMBIE_VOLUME[groan] *
                                  _zombie_gain(distance, occluded), pan)

    def _update_regular_step(self, distance, occluded, stride, pan, patrol_step):
        patrol_steps = patrol_step is not None
        if self._patrol_steps != patrol_steps:
            self._stop_channel("zombie_step")
            self._step_distance = 0.0
            self._patrol_steps = patrol_steps
        self._step_distance += patrol_step.stride if patrol_steps else stride
        step_due = self._step_distance >= _STEP_SPACING
        if step_due:
            self._step_distance %= _STEP_SPACING
        step_volume = (patrol_step.volume if patrol_steps else
                       _ZOMBIE_VOLUME["zombie_step"] * _zombie_gain(distance, occluded))
        step_pan = patrol_step.pan if patrol_steps else pan
        self._update_zombie_sound("zombie_step", step_due, step_volume, step_pan)

    def _switch_footstep_mode(self, directional):
        self._directional_mode = directional
        if not directional:
            self._stop_directional_steps()
            return
        self._stop_channel("zombie_step")
        self._step_distance = 0.0
        self._patrol_steps = False
        self._stop_heavy_step()
        # Legacy effects use chunk gain. A shared chunk has unity gain for independent channels.
        for kind in ("zombie_step", _HEAVY_STEP_SOUND):
            if (sound := self._sounds.get(kind)) is not None:
                p.Mix_VolumeChunk(sound, _MIX_MAX_VOLUME)

    def _update_directional_steps(self, dt, sources):
        heard = {}
        for source in sources:
            distance = source.distance
            limit = _PATROL_STEP_RANGE if source.kind == "patrol" else _HEARING_RANGE
            if not 0 <= distance < limit:
                continue
            sample = _HEAVY_STEP_SOUND if source.kind == "heavy" else "zombie_step"
            if sample in self._sounds:
                heard[sample, source.source_id] = source
        for side, owner in tuple(self._footstep_tails.items()):
            if not self._playing(self._channels.get(owner), self._sounds[owner[0]]):
                self._channels.pop(owner, None)
                del self._footstep_tails[side]
        elapsed = dt if math.isfinite(dt) and dt > 0 else 0.0
        for owner in self._footstep_progress.keys() - heard.keys():
            progress = self._footstep_progress[owner]
            progress.idle += elapsed
            if progress.idle >= _STEP_IDLE_GRACE:
                del self._footstep_progress[owner]
        for owner, source in heard.items():
            sample = owner[0]
            heavy = sample == _HEAVY_STEP_SOUND
            spacing = _HEAVY_STEP_SPACING if heavy else _STEP_SPACING
            stride = source.stride if math.isfinite(source.stride) and source.stride > 0 else 0.0
            progress = self._footstep_progress.setdefault(owner, _FootstepProgress())
            progress.idle = 0.0
            # Keep cadence by source, including when a channel is still finishing its last step.
            steps, progress.distance = divmod(progress.distance + stride, spacing)
            gain = (_patrol_volume(source.distance, source.occluded) if source.kind == "patrol" else
                    (_HEAVY_STEP_VOLUME if heavy else _ZOMBIE_VOLUME["zombie_step"])
                    * _zombie_gain(source.distance, source.occluded))
            volume = self._settings.effect_volume(round(gain))
            sound = self._sounds[sample]
            channel = self._channels.get(owner)
            if self._playing(channel, sound):
                p.Mix_Volume(channel, volume)
            else:
                self._channels.pop(owner, None)
                if steps and volume > 0:
                    side = int(source.pan >= 0.0)
                    previous = self._footstep_tails.pop(side, None)
                    if previous is not None:
                        self._stop_channel(previous)
                    if self._start_channel(owner, sound, source.pan, volume=volume) >= 0:
                        self._footstep_tails[side] = owner

    def _stop_directional_steps(self):
        for owner in self._footstep_tails.values():
            self._stop_channel(owner)
        self._footstep_tails.clear()
        self._footstep_progress.clear()

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
            p.Mix_VolumeChunk(sound, self._settings.effect_volume(max(1, round(volume))))
        if due and not playing:
            # Keep each sound on its starting side until its channel ends.
            self._start_channel(kind, sound, pan)

    def play_bottle_break(self, distance, *, pan=0.0):
        self._play_effect(_BOTTLE_SOUND, distance, pan=pan)

    def play_bottle_throw(self):
        self._play_effect(_BOTTLE_THROW_SOUND, 0.0)

    def play_gate_open(self, distance, *, pan=0.0):
        self._play_effect(_GATE_SOUND, distance, pan=pan)

    def play_shutter_close(self, distance, *, pan=0.0):
        self._play_effect(_SHUTTER_SOUND, distance, pan=pan)

    def play_bridge_motor(self, distance, *, pan=0.0):
        self._play_effect(_BRIDGE_MOTOR_SOUND, distance, pan=pan)

    def play_bus_broadcast(self, distance, *, pan=0.0):
        self._play_effect(_BUS_BROADCAST_SOUND, distance, pan=pan)

    def play_truck_cue(self, phase, distance, *, pan=0.0):
        sound = _TRUCK_CUES.get(phase)
        if sound is not None:
            self._play_effect(sound, distance, pan=pan)

    def play_vehicle_alarm(self, distance, *, pan=0.0):
        self._play_effect(_VEHICLE_SOUND, distance, pan=pan)

    def play_vehicle_hit(self, distance, *, pan=0.0):
        self._play_effect(_VEHICLE_HIT_SOUND, distance, pan=pan)

    def play_bat_swing(self):
        self._play_effect(_BAT_SWING_SOUND, 0.0)

    def play_bat_break(self):
        self._play_effect(_BAT_BREAK_SOUND, 0.0)

    def play_fist_hit(self):
        self._play_effect(_FIST_HIT_SOUND, 0.0)

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
        volume = max(1, round(_EFFECT_VOLUME[kind] * gain))
        p.Mix_VolumeChunk(sound, self._settings.effect_volume(volume))
        self._start_channel(kind, sound, pan)

    def _start_channel(self, kind, sound, pan, *, volume=_MIX_MAX_VOLUME):
        channel = p.Mix_PlayChannelTimed(-1, sound, 0, -1)
        if channel >= 0:
            for prior, owned in tuple(self._channels.items()):
                if owned == channel:
                    del self._channels[prior]
            p.Mix_Volume(channel, volume)
            pan = max(-1.0, min(1.0, pan)) if math.isfinite(pan) else 0.0
            far = round(255 - (255 - _PAN_FAR_GAIN) * abs(pan))
            left, right = (far, 255) if pan > 0 else (255, far)
            # Centered effects also clear any panning on a reused mixer channel.
            p.Mix_SetPanning(channel, left, right)
            self._channels[kind] = channel
        return channel

    def _stop_channel(self, kind):
        channel = self._channels.pop(kind, None)
        sample = kind[0] if isinstance(kind, tuple) else kind
        if self._playing(channel, self._sounds.get(sample)):
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

    def _stop_effects(self, preserve_map_cue, *, preserve_truck_cues=False):
        self._stop_regular_zombies()
        self._stop_heavy_step()
        self._stop_directional_steps()
        self._player_step_phase = 0.0
        for kind in _EFFECT_VOLUME:
            if (preserve_map_cue and kind == _MAP_SOUND) or (preserve_truck_cues and kind in _TRUCK_SOUNDS):
                continue
            self._stop_channel(kind)

    def stop(self):
        self._stop_effects(False)

    def close(self):
        self.stop()
        for sound in self._sounds.values():
            p.Mix_FreeChunk(sound)
        self._sounds.clear()
