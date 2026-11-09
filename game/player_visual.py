"""R1-B facing/stride atlas anchored to the ground contact point."""
from __future__ import annotations

import json
import math
from pathlib import Path

import pico2d.pico2d as p
from locomotion import Locomotion, STRIDE_DISTANCE, select_facing


METADATA_PATH = Path(__file__).resolve().parent / "assets/player/r1b-courier-atlas-20261104.json"
PARCEL_OCCLUDED_FACINGS = {"back", "back_right"}


def load_atlas(path, canvas_size):
    if not path.is_file():
        raise FileNotFoundError(f"R1-B sprite source not found: {path}")
    image = p.load_image(str(path))
    if [image.w, image.h] != canvas_size:
        raise ValueError(f"R1-B source canvas differs from metadata: {path}")
    if p.SDL_SetTextureScaleMode(image.texture, p.SDL_ScaleModeNearest) != 0:
        raise RuntimeError(f"R1-B nearest sampling failed: {p.SDL_GetError()!r}")
    return image


def load_empty_atlas(path, canvas_size):
    return load_atlas(path.with_stem(path.stem + "-empty"), canvas_size)


def sprite_rect(foot_x, foot_y, clip, pivot, display_height):
    """Return destination left/bottom/width/height in pico2d screen px."""
    left, top, width, height = clip
    scale = display_height / height
    return (foot_x - (pivot[0] - left) * scale,
            foot_y - (height - (pivot[1] - top)) * scale,
            width * scale, height * scale)


class PlayerVisual:
    display_scale = 1.0
    sprinting = False

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
                self.images[source_id] = load_atlas(path, source["canvas_size"])
        except Exception:
            self.close()
            raise

    def update(self, aim_angle, dx, dy, *, sprinting=False):
        sprint = self.metadata.get("sprint")
        previous = self.locomotion.facing if self.locomotion._initialized else None
        use_sprint = (sprinting and sprint is not None and "sprint" in self.images and dx > 0 > dy
                      and select_facing(aim_angle, previous) == sprint["facing"]
                      and select_facing(math.atan2(dy, dx)) == sprint["facing"])
        stride = sprint["stride_distance"] if use_sprint else STRIDE_DISTANCE
        self.locomotion.update(aim_angle, dx, dy, reverse_backstep=True, stride_distance=stride)
        self.sprinting = use_sprint and self.locomotion.moving

    def load_delivery_sprites(self):
        sources = self.metadata["sources"]
        active = dict.fromkeys(frame["source"] for facing, frames in self.metadata["frames"].items()
                               if facing not in PARCEL_OCCLUDED_FACINGS for frame in frames)
        for key in active:
            source = sources[key]
            self.empty_images[key] = load_empty_atlas(METADATA_PATH.parent / source["image"], source["canvas_size"])
        sprint = self.metadata.get("sprint")
        if sprint is not None:
            path = METADATA_PATH.parent / sprint["image"]
            self.images["sprint"] = load_atlas(path, sprint["canvas_size"])
            self.empty_images["sprint"] = load_empty_atlas(path, sprint["canvas_size"])

    @property
    def frame_index(self):
        frames = self.metadata["frames"][self.locomotion.facing]
        return self.locomotion.walk_frame_index(len(frames) - 1)

    def draw(self, foot_x, foot_y, *, empty_handed=False):
        frames = self.metadata["frames"][self.locomotion.facing]
        frame = frames[self.frame_index]
        key = "sprint" if self.sprinting else frame.get("source", "atlas")
        images = self.empty_images if empty_handed and key in self.empty_images else self.images
        image = images[key]
        # Sprint cells share the walking order, grid and ground pivots.
        clip = frame["cell_topleft"] if self.sprinting else frame["clip_topleft"]
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
