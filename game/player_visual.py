"""R1-A fixed-pose sprite anchored to its ground contact midpoint."""
from __future__ import annotations

import json
from pathlib import Path

import pico2d.pico2d as p


METADATA_PATH = Path(__file__).resolve().parent / "assets/player/r1a-courier-20261104.json"


def sprite_rect(foot_x, foot_y, clip, pivot, display_height):
    """Return destination left/bottom/width/height in pico2d screen px."""
    left, top, width, height = clip
    scale = display_height / height
    return (foot_x - (pivot[0] - left) * scale,
            foot_y - (height - (pivot[1] - top)) * scale,
            width * scale, height * scale)


class PlayerVisual:
    def __init__(self):
        self.image = None
        self.metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        path = METADATA_PATH.parent / self.metadata["image"]
        if not path.is_file():
            raise FileNotFoundError(f"R1-A sprite not found: {path}")
        self.image = p.load_image(str(path))
        if [self.image.w, self.image.h] != self.metadata["canvas_size"]:
            self.close()
            raise ValueError(f"R1-A sprite canvas differs from metadata: {path}")

    def draw(self, foot_x, foot_y):
        clip = self.metadata["clip_topleft"]
        left, bottom, width, height = sprite_rect(
            foot_x, foot_y, clip, self.metadata["foot_pivot_topleft"],
            self.metadata["display_height"])
        src_x, src_top, src_width, src_height = clip
        # Fixed pose: no rotation or mirroring. Only runtime clipping/scaling.
        self.image.clip_draw(
            src_x, self.image.h - src_top - src_height, src_width, src_height,
            left + width / 2, bottom + height / 2, width, height)

    def close(self):
        # Image.__del__ alone owns the texture; never destroy it twice.
        self.image = None
