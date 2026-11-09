"""R2-C8 directional sprites; combat time belongs to CombatWorld."""
from __future__ import annotations

import json
import math
from pathlib import Path

import pico2d.pico2d as p

from player_visual import sprite_rect
from combat import ATTACK_HIT_TIME, STUN_DURATION, ZOMBIE_ATTACK_DURATION
from locomotion import Locomotion, STRIDE_DISTANCE, select_facing


METADATA_PATH = Path(__file__).resolve().parent / "assets/combat/r2a-combat-20261106.json"
ZOMBIE_METADATA_PATH = Path(__file__).resolve().parent / "assets/zombie/r2z-zombie-20261106.json"
ZOMBIE_ATTACK_METADATA_PATH = Path(__file__).resolve().parent / "assets/zombie/r2za-zombie-attack-20261106.json"
_ZOMBIE_RESUME_DISTANCE = 8.0
_DISTANCE_EPSILON = 1e-9
_STATIONARY_FRONT_RIGHT_SOURCE = "attack_stationary_front_right"


def _locked_walk_boundary(legacy_time, hit_time):
    # Map authored boundaries to the locked clock so exact hits and nextafter
    # samples land on opposite sides even when float subtraction would round.
    if legacy_time < ATTACK_HIT_TIME:
        locked_time = legacy_time * hit_time / ATTACK_HIT_TIME
    else:
        locked_time = legacy_time + (hit_time - ATTACK_HIT_TIME)
    return round(locked_time, 12)


class CombatVisual:
    def __init__(self):
        self.metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        self.metadata["zombie"] = json.loads(ZOMBIE_METADATA_PATH.read_text(encoding="utf-8"))
        self.metadata["zombie_attack"] = json.loads(ZOMBIE_ATTACK_METADATA_PATH.read_text(encoding="utf-8"))
        self.images = {}
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
        locked = attack.facing == "front_right" and getattr(attack, "stationary_front_right", False)
        source_name = (_STATIONARY_FRONT_RIGHT_SOURCE if locked and not walking
                       else self._attack_source(attack.facing))
        if source_name not in self.metadata:
            return None
        for index, frame in enumerate(self.metadata[source_name]["frames"]):
            start, end = frame["start"], frame["end"]
            if locked and walking:
                start = _locked_walk_boundary(start, attack.hit_time)
                end = _locked_walk_boundary(end, attack.hit_time)
            if start <= elapsed < end:
                return source_name, index
        return None

    def attack_frame_index(self, attack):
        step = self._attack_step(attack)
        return step[1] if step is not None else None

    def _draw(self, source_name, frame, foot_x, foot_y):
        image = self.images[source_name]
        scale = self.metadata[source_name]["scale"]
        clip = frame["clip_topleft"]
        left, bottom, width, height = sprite_rect(
            foot_x, foot_y, clip, frame["foot_pivot_topleft"], clip[3] * scale)
        x, top, w, h = clip
        image.clip_draw(x, image.h - top - h, w, h,
                        left + width / 2, bottom + height / 2, width, height)

    def draw_attack(self, attack, foot_x, foot_y, walk_frame_index=None):
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
        self._draw(source_name, self.metadata[source_name]["frames"][index], foot_x, foot_y)
        return True

    @staticmethod
    def zombie_state(zombie):
        if not zombie.alive:
            return "dead"
        if zombie.stun_remaining > 0:
            return "stunned"
        return "attacking" if zombie.attack is not None else "alive"

    def reset_zombie_animation(self):
        self.zombie_locomotion = Locomotion()
        self._zombie_attack = None
        self._zombie_attack_facing = None
        self._zombie_resume = None

    def update_zombie(self, zombie, dx, dy, *, paused=False):
        motion = self.zombie_locomotion
        can_walk = zombie.alive and zombie.stun_remaining <= 0 and zombie.attack is None
        if paused and can_walk and self._zombie_resume is not None:
            return
        previous_facing = motion.facing if motion._initialized else None
        previous_phase = motion.phase
        recoil_x, recoil_y = zombie.recoil_offset
        dx, dy = dx - recoil_x, dy - recoil_y
        motion.update(zombie.aim_angle, dx, dy)

        if not can_walk:
            attack = zombie.attack if zombie.alive and zombie.stun_remaining <= 0 else None
            if attack is not None:
                if attack is not self._zombie_attack:
                    self._zombie_attack_facing = (select_facing(attack.angle, previous_facing)
                                                  if previous_facing is not None else attack.facing)
                motion.facing = self._zombie_attack_facing
            self._zombie_attack = attack
            self._zombie_resume = None
            motion.moving = False
            return

        if self._zombie_attack is not None:
            if self._zombie_attack.elapsed >= ZOMBIE_ATTACK_DURATION:
                poses = self.metadata["zombie"]["facings"][motion.facing]
                if poses.get("resume"):
                    self._zombie_resume = (0.0, None)
            self._zombie_attack = None
        if self._zombie_resume is None:
            return
        distance, target = self._zombie_resume
        if not motion.moving:
            if distance > 0:
                self._zombie_resume = None
            return
        distance += math.hypot(dx, dy)
        if distance + _DISTANCE_EPSILON >= _ZOMBIE_RESUME_DISTANCE:
            self._zombie_resume = None
            return
        if target is None:
            # The destination is the regular walk frame reached after 8px.
            target_phase = (previous_phase + _ZOMBIE_RESUME_DISTANCE / STRIDE_DISTANCE) % 1.0
            target = Locomotion(phase=target_phase, moving=True).walk_frame_index(8) - 1
        self._zombie_resume = (distance, target)

    def _zombie_pose(self, zombie):
        source = self.metadata["zombie"]
        if not zombie.alive:
            return "zombie", source["frames"]["dead"]
        poses = source["facings"][self.zombie_locomotion.facing]
        if zombie.stun_remaining > 0:
            # The combat clock alone determines the hit pose; no visual timer.
            for frame in poses["hit"]:
                if zombie.stun_remaining > STUN_DURATION - frame["end"]:
                    return "zombie", frame
            return "zombie", poses["hit"][-1]
        attack = zombie.attack
        if attack is not None:
            facing = self._zombie_attack_facing if attack is self._zombie_attack else attack.facing
            for frame in self.metadata["zombie_attack"]["facings"][facing]:
                if frame["start"] <= attack.elapsed < frame["end"]:
                    return "zombie_attack", frame
        walk = self.zombie_locomotion.walk_frame_index(8)
        resume = poses.get("resume")
        if walk and resume and self._zombie_resume is not None:
            distance, target = self._zombie_resume
            if target is not None:
                step = int(distance + _DISTANCE_EPSILON >= _ZOMBIE_RESUME_DISTANCE / 2)
                return "zombie", resume[target][step]
        return "zombie", poses["walk"][walk - 1] if walk else poses["idle"]

    def _zombie_frame(self, zombie):
        return self._zombie_pose(zombie)[1]

    def draw_zombie(self, zombie, foot_x, foot_y):
        source, frame = self._zombie_pose(zombie)
        self._draw(source, frame, foot_x, foot_y)

    def zombie_contains(self, zombie, foot_x, foot_y, screen_x, screen_y):
        """Pick the living sprite's actual opaque pixels, excluding cell padding."""
        if not zombie.alive:
            return False
        source_name, frame = self._zombie_pose(zombie)
        source = self.metadata[source_name]
        clip, scale = frame["clip_topleft"], source["scale"]
        left, bottom, width, height = sprite_rect(
            foot_x, foot_y, clip, frame["foot_pivot_topleft"], clip[3] * scale)
        if not (left <= screen_x < left + width and bottom <= screen_y < bottom + height):
            return False
        x = int((screen_x - left) // scale)
        y = clip[3] - 1 - int((screen_y - bottom) // scale)
        return any(start <= x <= end for start, end in frame["opaque_rows"].get(str(y), ()))

    def close(self):
        self.images.clear()
