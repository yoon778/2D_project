"""R1-B facing/stride atlas anchored to the ground contact point."""
from __future__ import annotations

import json
from pathlib import Path

import pico2d.pico2d as p
from locomotion import Locomotion


METADATA_PATH = Path(__file__).resolve().parent / "assets/player/r1b-courier-atlas-20261104.json"
PARCEL_OCCLUDED_FACINGS = {"back", "back_right"}


def load_empty_atlas(path, canvas_size):
    variant = path.with_stem(path.stem + "-empty")
    image = p.load_image(str(variant))
    if [image.w, image.h] != canvas_size:
        raise ValueError(f"Empty-handed sprite canvas differs from metadata: {variant}")
    if p.SDL_SetTextureScaleMode(image.texture, p.SDL_ScaleModeNearest) != 0:
        raise RuntimeError(f"Empty-handed nearest sampling failed: {p.SDL_GetError()!r}")
    return image


def sprite_rect(foot_x, foot_y, clip, pivot, display_height):
    """Return destination left/bottom/width/height in pico2d screen px."""
    left, top, width, height = clip
    scale = display_height / height
    return (foot_x - (pivot[0] - left) * scale,
            foot_y - (height - (pivot[1] - top)) * scale,
            width * scale, height * scale)


class PlayerVisual:
    display_scale = 1.0

    def __init__(self):
        self.images = {}
        self.empty_images = {}
        self.locomotion = Locomotion()
        self.metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        sources = {"atlas": self.metadata, **self.metadata.get("sources", {})}
        active_sources = dict.fromkeys(
            frame.get("source", "atlas")
            for frames in self.metadata["frames"].values()
            for frame in frames
        )
        try:
            for source_id in active_sources:
                source = sources[source_id]
                path = METADATA_PATH.parent / source["image"]
                if not path.is_file():
                    raise FileNotFoundError(f"R1-B sprite source not found: {path}")
                self.images[source_id] = p.load_image(str(path))
                if [self.images[source_id].w, self.images[source_id].h] != source["canvas_size"]:
                    raise ValueError(f"R1-B source canvas differs from metadata: {path}")
                if p.SDL_SetTextureScaleMode(self.images[source_id].texture, p.SDL_ScaleModeNearest) != 0:
                    raise RuntimeError(f"R1-B nearest sampling failed: {p.SDL_GetError()!r}")
        except Exception:
            self.close()
            raise

    def update(self, aim_angle, dx, dy):
        self.locomotion.update(aim_angle, dx, dy, reverse_backstep=True)

    def load_empty_hands(self):
        sources = self.metadata["sources"]
        active = dict.fromkeys(frame["source"] for facing, frames in self.metadata["frames"].items()
                               if facing not in PARCEL_OCCLUDED_FACINGS for frame in frames)
        for key in active:
            source = sources[key]
            self.empty_images[key] = load_empty_atlas(METADATA_PATH.parent / source["image"], source["canvas_size"])

    @property
    def frame_index(self):
        frames = self.metadata["frames"][self.locomotion.facing]
        return self.locomotion.walk_frame_index(len(frames) - 1)

    def draw(self, foot_x, foot_y, *, empty_handed=False):
        frames = self.metadata["frames"][self.locomotion.facing]
        frame = frames[self.frame_index]
        key = frame.get("source", "atlas")
        images = self.empty_images if empty_handed and key in self.empty_images else self.images
        image = images[key]
        clip = frame["clip_topleft"]
        # Keep the idle-based scale for all poses of this facing.
        reference_height = frame.get("scale_reference_height", frames[0]["clip_topleft"][3])
        shown_height = clip[3] * self.metadata["display_height"] / reference_height * self.display_scale
        left, bottom, width, height = sprite_rect(
            foot_x, foot_y, clip, frame["foot_pivot_topleft"], shown_height)
        src_x, src_top, src_width, src_height = clip
        # Each facing has its own art; never rotate or mirror the atlas.
        image.clip_draw(
            src_x, image.h - src_top - src_height, src_width, src_height,
            left + width / 2, bottom + height / 2, width, height)

    def close(self):
        # Image.__del__ alone owns the texture; never destroy it twice.
        self.images.clear()
        self.empty_images.clear()
