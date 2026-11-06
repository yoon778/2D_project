"""R2-A attack and temporary zombie sprites; combat time belongs to CombatWorld."""
from __future__ import annotations

import json
import math
from pathlib import Path

import pico2d.pico2d as p

from player_visual import sprite_rect


METADATA_PATH = Path(__file__).resolve().parent / "assets/combat/r2a-combat-20261106.json"


class CombatVisual:
    def __init__(self):
        self.metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        self.images = {}
        try:
            for key in ("attack", "zombie", "attack_walk"):
                source = self.metadata[key]
                image = p.load_image(str(METADATA_PATH.parent / source["image"]))
                self.images[key] = image
                if [image.w, image.h] != source["canvas_size"]:
                    raise ValueError(f"R2-A canvas differs from metadata: {key}")
                if p.SDL_SetTextureScaleMode(image.texture, p.SDL_ScaleModeNearest) != 0:
                    raise RuntimeError(f"R2-A nearest sampling failed: {p.SDL_GetError()!r}")
        except Exception:
            self.close()
            raise

    def attack_frame_index(self, attack):
        if attack is None or attack.facing != self.metadata["attack"]["facing"]:
            return None
        elapsed = attack.elapsed
        if not math.isfinite(elapsed):
            return None
        for index, frame in enumerate(self.metadata["attack"]["frames"]):
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
        if walk_frame_index:
            frame = self.metadata["attack_walk"]["frames"][index * 8 + walk_frame_index - 1]
            self._draw("attack_walk", frame, foot_x, foot_y)
        else:
            self._draw("attack", self.metadata["attack"]["frames"][index], foot_x, foot_y)
        return True

    @staticmethod
    def zombie_state(zombie):
        if not zombie.alive:
            return "dead"
        return "stunned" if zombie.stun_remaining > 0 else "alive"

    def draw_zombie(self, zombie, foot_x, foot_y):
        frame = self.metadata["zombie"]["frames"][self.zombie_state(zombie)]
        self._draw("zombie", frame, foot_x, foot_y)

    def zombie_contains(self, zombie, foot_x, foot_y, screen_x, screen_y):
        """Pick the living sprite's actual opaque pixels, excluding cell padding."""
        if not zombie.alive:
            return False
        source = self.metadata["zombie"]
        frame = source["frames"]["alive"]
        clip, scale = frame["clip_topleft"], source["scale"]
        left, bottom, width, height = sprite_rect(
            foot_x, foot_y, clip, frame["foot_pivot_topleft"], clip[3] * scale)
        if not (left <= screen_x < left + width and bottom <= screen_y < bottom + height):
            return False
        x = int((screen_x - left) // scale)
        y = clip[3] - 1 - int((screen_y - bottom) // scale)
        return any(start <= x <= end for start, end in source["opaque_rows"].get(str(y), ()))

    def close(self):
        self.images.clear()
