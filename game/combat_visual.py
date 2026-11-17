"""R2-C8 directional sprites; combat time belongs to CombatWorld."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
from pathlib import Path

import pico2d.pico2d as p

from player_visual import PARCEL_OCCLUDED_FACINGS, load_atlas, load_empty_atlas, sprite_rect
from combat import ATTACK_HIT_TIME, HEAVY_ZOMBIE_APPEARANCE, ZOMBIE_APPEARANCES
from locomotion import Locomotion, STRIDE_DISTANCE, select_facing


METADATA_PATH = Path(__file__).resolve().parent / "assets/combat/r2a-combat-20261106.json"
ZOMBIE_METADATA_PATH = Path(__file__).resolve().parent / "assets/zombie/r2z-zombie-20261106.json"
ZOMBIE_ATTACK_METADATA_PATH = Path(__file__).resolve().parent / "assets/zombie/r2za-zombie-attack-20261106.json"
_ZOMBIE_RESUME_DISTANCE = 8.0
_DISTANCE_EPSILON = 1e-9


@dataclass
class ZombieMotion:
    locomotion: Locomotion = field(default_factory=Locomotion)
    attack: object = None
    attack_facing: str | None = None
    resume: tuple[float, int | None] | None = None


def _locked_walk_boundary(legacy_time, hit_time):
    # Map authored boundaries to the locked clock so exact hits and nextafter
    # samples land on opposite sides even when float subtraction would round.
    if legacy_time < ATTACK_HIT_TIME:
        locked_time = legacy_time * hit_time / ATTACK_HIT_TIME
    else:
        locked_time = legacy_time + (hit_time - ATTACK_HIT_TIME)
    return round(locked_time, 12)


class CombatVisual:
    display_scale = 1.0

    def __init__(self):
        self.metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        self.metadata["zombie"] = json.loads(ZOMBIE_METADATA_PATH.read_text(encoding="utf-8"))
        self.metadata["zombie_attack"] = json.loads(ZOMBIE_ATTACK_METADATA_PATH.read_text(encoding="utf-8"))
        self.images = {}
        self.empty_images = {}
        self.reset_zombie_animation()
        try:
            for key, source in self.metadata.items():
                path = {"zombie": ZOMBIE_METADATA_PATH, "zombie_attack": ZOMBIE_ATTACK_METADATA_PATH}.get(
                    key, METADATA_PATH)
                directory = path.parent
                image = p.load_image(str(directory / source["image"]))
                self.images[key] = image
                if [image.w, image.h] != source["canvas_size"]:
                    raise ValueError(f"R2-C8 canvas differs from metadata: {key}")
                if p.SDL_SetTextureScaleMode(image.texture, p.SDL_ScaleModeNearest) != 0:
                    raise RuntimeError(f"R2-C8 nearest sampling failed: {p.SDL_GetError()!r}")
        except Exception:
            self.close()
            raise

    def load_zombie_appearances(self):
        """Load the delivery atlases and the heavy zombie's own pose data once."""
        if f"{ZOMBIE_APPEARANCES[1]}_zombie" in self.images:
            return
        images = {}
        metadata = {}
        for appearance in (*ZOMBIE_APPEARANCES[1:], HEAVY_ZOMBIE_APPEARANCE):
            for source, suffix in (("zombie", "base"), ("zombie_attack", "attack")):
                key = f"{appearance}_{source}"
                layout = self.metadata[source]
                path = ZOMBIE_METADATA_PATH.parent / f"{appearance}-{suffix}.png"
                if appearance == HEAVY_ZOMBIE_APPEARANCE:
                    layout = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
                images[key] = load_atlas(path, layout["canvas_size"])
                metadata[key] = layout
        self.images.update(images)
        self.metadata.update(metadata)

    def _attack_source(self, facing, walking=False):
        name = "attack_walk" if walking else "attack"
        if facing != self.metadata["attack"]["facing"]:
            name += f"_{facing}"
        source = self.metadata.get(name)
        return name if source is not None and source["facing"] == facing else None

    def _attack_step(self, attack, walking=False):
        if attack is None:
            return None
        elapsed = attack.elapsed
        if not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed):
            return None
        authored = attack.facing == "front_right" and getattr(attack, "stationary_front_right", False)
        locked = authored or getattr(attack, "stationary_swing", False)
        stationary = f"attack_stationary_{attack.facing}"
        use_stationary = locked and not walking and stationary in self.metadata
        source_name = stationary if use_stationary else self._attack_source(attack.facing)
        if source_name not in self.metadata:
            return None
        for index, frame in enumerate(self.metadata[source_name]["frames"]):
            start, end = frame["start"], frame["end"]
            if locked and not use_stationary:
                start = _locked_walk_boundary(start, attack.hit_time)
                end = _locked_walk_boundary(end, attack.hit_time)
            if start <= elapsed < end:
                return source_name, index
        return None

    def attack_frame_index(self, attack):
        step = self._attack_step(attack)
        return step[1] if step is not None else None

    def load_empty_hands(self):
        for key, source in self.metadata.items():
            if key.startswith("attack") and source["facing"] not in PARCEL_OCCLUDED_FACINGS:
                self.empty_images[key] = load_empty_atlas(
                    METADATA_PATH.parent / source["image"], source["canvas_size"])

    def _draw(self, source_name, frame, foot_x, foot_y, *, empty_handed=False):
        images = self.empty_images if empty_handed and source_name in self.empty_images else self.images
        image = images[source_name]
        scale = self.metadata[source_name]["scale"] * self.display_scale
        clip = frame["clip_topleft"]
        left, bottom, width, height = sprite_rect(
            foot_x, foot_y, clip, frame["foot_pivot_topleft"], clip[3] * scale)
        x, top, w, h = clip
        image.clip_draw(x, image.h - top - h, w, h,
                        left + width / 2, bottom + height / 2, width, height)

    def draw_attack(self, attack, foot_x, foot_y, walk_frame_index=None, *, empty_handed=False):
        step = self._attack_step(attack, bool(walk_frame_index))
        if step is None:
            return False
        if walk_frame_index is not None and (type(walk_frame_index) is not int
                                              or not 0 <= walk_frame_index <= 8):
            raise ValueError("walk_frame_index must be None or an integer from 0 to 8")
        source_name, index = step
        if walk_frame_index:
            source_name = self._attack_source(attack.facing, walking=True)
            if source_name is None:
                return False
            index = index * 8 + walk_frame_index - 1
        frame = self.metadata[source_name]["frames"][index]
        if getattr(attack, "landed", False):
            frame = frame.get("on_hit", frame)
        self._draw(source_name, frame, foot_x, foot_y, empty_handed=empty_handed)
        return True

    def reset_zombie_animation(self):
        self._primary_motion = ZombieMotion()
        self._zombie_motions = {}

    @property
    def zombie_locomotion(self):
        return self._primary_motion.locomotion

    def _motion_for(self, zombie):
        key = id(zombie)
        if key not in self._zombie_motions:
            self._zombie_motions[key] = ZombieMotion() if self._zombie_motions else self._primary_motion
        return self._zombie_motions[key]

    def update_zombie(self, zombie, dx, dy, *, paused=False):
        state = self._motion_for(zombie)
        motion = state.locomotion
        can_walk = zombie.alive and zombie.stun_remaining <= 0 and zombie.attack is None
        if paused and can_walk and state.resume is not None:
            return
        previous_facing = motion.facing if motion._initialized else None
        previous_phase = motion.phase
        recoil_x, recoil_y = zombie.recoil_offset
        dx, dy = dx - recoil_x, dy - recoil_y
        motion.update(zombie.aim_angle, dx, dy)

        if not can_walk:
            attack = zombie.attack if zombie.alive and zombie.stun_remaining <= 0 else None
            if attack is not None:
                if attack is not state.attack:
                    state.attack_facing = (select_facing(attack.angle, previous_facing)
                                           if previous_facing is not None else attack.facing)
                motion.facing = state.attack_facing
            state.attack = attack
            state.resume = None
            motion.moving = False
            return

        if state.attack is not None:
            if state.attack.elapsed >= state.attack.duration:
                poses = self.metadata["zombie"]["facings"][motion.facing]
                if poses.get("resume"):
                    state.resume = (0.0, None)
            state.attack = None
        if state.resume is None:
            return
        distance, target = state.resume
        if not motion.moving:
            if distance > 0:
                state.resume = None
            return
        distance += math.hypot(dx, dy)
        if distance + _DISTANCE_EPSILON >= _ZOMBIE_RESUME_DISTANCE:
            state.resume = None
            return
        if target is None:
            # The destination is the regular walk frame reached after 8px.
            target_phase = (previous_phase + _ZOMBIE_RESUME_DISTANCE / STRIDE_DISTANCE) % 1.0
            target = Locomotion(phase=target_phase, moving=True).walk_frame_index(8) - 1
        state.resume = (distance, target)

    def _zombie_pose(self, zombie):
        prefix = "" if zombie.appearance == "classic" else f"{zombie.appearance}_"
        base_name = f"{prefix}zombie"
        source = self.metadata[base_name]
        if not zombie.alive:
            return base_name, source["frames"]["dead"]
        state = self._motion_for(zombie)
        poses = source["facings"][state.locomotion.facing]
        if zombie.stun_remaining > 0:
            # Short hits fit the authored recoil and return into the combat clock.
            frames = poses["hit"]
            duration = zombie.stun_duration
            scale = min(1.0, duration / frames[-1]["end"])
            for frame in frames:
                if zombie.stun_remaining > duration - frame["end"] * scale:
                    return base_name, frame
            return base_name, frames[-1]
        attack = zombie.attack
        if attack is not None:
            attack_name = f"{prefix}zombie_attack"
            facing = state.attack_facing if attack is state.attack else attack.facing
            for frame in self.metadata[attack_name]["facings"][facing]:
                if frame["start"] <= attack.elapsed < frame["end"]:
                    return attack_name, frame
        walk = state.locomotion.walk_frame_index(8)
        resume = poses.get("resume")
        if walk and resume and state.resume is not None:
            distance, target = state.resume
            if target is not None:
                step = int(distance + _DISTANCE_EPSILON >= _ZOMBIE_RESUME_DISTANCE / 2)
                return base_name, resume[target][step]
        return base_name, poses["walk"][walk - 1] if walk else poses["idle"]

    def _zombie_frame(self, zombie):
        return self._zombie_pose(zombie)[1]

    def draw_zombie(self, zombie, foot_x, foot_y):
        source, frame = self._zombie_pose(zombie)
        self._draw(source, frame, foot_x, foot_y)

    def zombie_texture(self, zombie):
        source, _ = self._zombie_pose(zombie)
        return self.images[source].texture

    def zombie_rect(self, zombie, foot_x, foot_y):
        source_name, frame = self._zombie_pose(zombie)
        clip = frame["clip_topleft"]
        scale = self.metadata[source_name]["scale"] * self.display_scale
        return sprite_rect(foot_x, foot_y, clip, frame["foot_pivot_topleft"], clip[3] * scale)

    def zombie_contains(self, zombie, foot_x, foot_y, screen_x, screen_y):
        """Pick the living sprite's actual opaque pixels, excluding cell padding."""
        if not zombie.alive:
            return False
        source_name, frame = self._zombie_pose(zombie)
        source = self.metadata[source_name]
        clip, scale = frame["clip_topleft"], source["scale"] * self.display_scale
        left, bottom, width, height = sprite_rect(
            foot_x, foot_y, clip, frame["foot_pivot_topleft"], clip[3] * scale)
        if not (left <= screen_x < left + width and bottom <= screen_y < bottom + height):
            return False
        x = int((screen_x - left) // scale)
        y = clip[3] - 1 - int((screen_y - bottom) // scale)
        return any(start <= x <= end for start, end in frame["opaque_rows"].get(str(y), ()))

    def close(self):
        self.images.clear()
        self.empty_images.clear()
