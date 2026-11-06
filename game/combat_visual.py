"""R2-C8 directional sprites; combat time belongs to CombatWorld."""
from __future__ import annotations

import json
import math
from pathlib import Path

import pico2d.pico2d as p

from player_visual import sprite_rect
from combat import STUN_DURATION
from locomotion import Locomotion


METADATA_PATH = Path(__file__).resolve().parent / "assets/combat/r2a-combat-20261106.json"
ZOMBIE_METADATA_PATH = Path(__file__).resolve().parent / "assets/zombie/r2z-zombie-20261106.json"


class CombatVisual:
    def __init__(self):
        self.metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        self.metadata["zombie"] = json.loads(ZOMBIE_METADATA_PATH.read_text(encoding="utf-8"))
        self.images = {}
        self.reset_zombie_animation()
        try:
            for key, source in self.metadata.items():
                directory = ZOMBIE_METADATA_PATH.parent if key == "zombie" else METADATA_PATH.parent
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

    def attack_frame_index(self, attack):
        if attack is None:
            return None
        source_name = self._attack_source(attack.facing)
        if source_name is None:
            return None
        elapsed = attack.elapsed
        if not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed):
            return None
        for index, frame in enumerate(self.metadata[source_name]["frames"]):
            if frame["start"] <= elapsed < frame["end"]:
                return index
        return None

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
        index = self.attack_frame_index(attack)
        if index is None:
            return False
        if walk_frame_index is not None and (type(walk_frame_index) is not int
                                              or not 0 <= walk_frame_index <= 8):
            raise ValueError("walk_frame_index must be None or an integer from 0 to 8")
        source_name = self._attack_source(attack.facing, bool(walk_frame_index))
        if source_name is None:
            return False
        frame_index = index * 8 + walk_frame_index - 1 if walk_frame_index else index
        self._draw(source_name, self.metadata[source_name]["frames"][frame_index], foot_x, foot_y)
        return True

    @staticmethod
    def zombie_state(zombie):
        if not zombie.alive:
            return "dead"
        return "stunned" if zombie.stun_remaining > 0 else "alive"

    def reset_zombie_animation(self):
        self.zombie_locomotion = Locomotion()

    def update_zombie(self, zombie, dx, dy):
        self.zombie_locomotion.update(zombie.aim_angle, dx, dy)
        if not zombie.alive or zombie.stun_remaining > 0:
            self.zombie_locomotion.moving = False

    def _zombie_frame(self, zombie):
        source = self.metadata["zombie"]
        if not zombie.alive:
            return source["frames"]["dead"]
        poses = source["facings"][self.zombie_locomotion.facing]
        if zombie.stun_remaining > 0:
            # The combat clock alone determines the hit pose; no visual timer.
            for frame in poses["hit"]:
                if zombie.stun_remaining > STUN_DURATION - frame["end"]:
                    return frame
            return poses["hit"][-1]
        walk = self.zombie_locomotion.walk_frame_index(8)
        return poses["walk"][walk - 1] if walk else poses["idle"]

    def draw_zombie(self, zombie, foot_x, foot_y):
        self._draw("zombie", self._zombie_frame(zombie), foot_x, foot_y)

    def zombie_contains(self, zombie, foot_x, foot_y, screen_x, screen_y):
        """Pick the living sprite's actual opaque pixels, excluding cell padding."""
        if not zombie.alive:
            return False
        source = self.metadata["zombie"]
        frame = self._zombie_frame(zombie)
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
