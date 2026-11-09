"""Verify real multi-source textures and cleanup using SDL dummy only."""
from collections import Counter
from contextlib import contextmanager
import ctypes
import gc
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pico2d.pico2d as p
import opening
import player_visual


def address(texture):
    return ctypes.cast(texture, ctypes.c_void_p).value


def active_sources(metadata):
    return list(dict.fromkeys(frame.get("source", "atlas")
                              for frames in metadata["frames"].values()
                              for frame in frames))


@contextmanager
def dummy_canvas():
    hint = p.SDL_HINT_RENDER_SCALE_QUALITY
    previous_hint = p.SDL_GetHint(hint)
    opened = False
    with patch.dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy",
                    SDL_RENDER_DRIVER="software"):
        try:
            if p.SDL_WasInit(p.SDL_INIT_VIDEO) and p.SDL_GetCurrentVideoDriver() != b"dummy":
                raise AssertionError("A non-dummy SDL video driver is already active")
            opened = True
            p.open_canvas(1280, 720, sync=False)
            if not p.renderer:
                p.renderer = p.SDL_CreateRenderer(p.window, -1, p.SDL_RENDERER_SOFTWARE)
            if not p.renderer or p.SDL_GetCurrentVideoDriver() != b"dummy":
                raise AssertionError(f"Dummy renderer initialization failed: {p.SDL_GetError()!r}")
            # Every loaded texture must override a deliberately linear default.
            if not p.SDL_SetHint(hint, b"1"):
                raise AssertionError("Unable to select linear default for sampling check")
            yield
        finally:
            if opened:
                p.close_canvas()
            if previous_hint is None:
                p.SDL_ResetHint(hint)
            else:
                p.SDL_SetHint(hint, previous_hint)


@contextmanager
def track_texture_destruction():
    original_destroy = p.SDL_DestroyTexture
    destroyed = Counter()

    def destroy(texture):
        key = address(texture)
        destroyed[key] += 1
        # Record duplicate release as failure evidence without double-freeing SDL.
        if destroyed[key] == 1:
            return original_destroy(texture)
        return None

    with patch.object(p, "SDL_DestroyTexture", side_effect=destroy):
        yield destroyed


class MultiSourceTextureTests(unittest.TestCase):
    def test_referenced_sources_match_canvas_and_override_linear_sampling(self):
        visual = None
        image = None
        with dummy_canvas():
            try:
                visual = player_visual.PlayerVisual()
                sources = active_sources(visual.metadata)
                self.assertEqual(set(visual.images), set(sources))
                self.assertLess(len(sources), len(visual.metadata["sources"]))
                for key in sources:
                    with self.subTest(source=key):
                        image = visual.images[key]
                        self.assertEqual(
                            [image.w, image.h], visual.metadata["sources"][key]["canvas_size"])
                        sampling = ctypes.c_int(-1)
                        result = p.SDL_GetTextureScaleMode(image.texture, ctypes.byref(sampling))
                        self.assertEqual(result, 0, p.SDL_GetError())
                        self.assertEqual(sampling.value, p.SDL_ScaleModeNearest)
                del image
            finally:
                image = None
                if visual is not None:
                    visual.close()

    def test_retired_source_may_be_missing_from_current_build(self):
        original = Path(player_visual.METADATA_PATH)
        metadata = json.loads(original.read_text(encoding="utf-8"))
        active = active_sources(metadata)
        for name, source in metadata["sources"].items():
            source["image"] = str(original.parent / source["image"]) if name in active else "missing.png"
        with tempfile.TemporaryDirectory(prefix="dead-route-active-sources-") as directory:
            path = Path(directory) / "player.json"
            for data in (metadata, {key: value for key, value in metadata.items()
                                    if key not in ("image", "canvas_size")}):
                with self.subTest(has_legacy_atlas="image" in data):
                    path.write_text(json.dumps(data), encoding="utf-8")
                    with dummy_canvas(), patch.object(player_visual, "METADATA_PATH", path):
                        visual = player_visual.PlayerVisual()
                        try:
                            self.assertEqual(list(visual.images), active)
                            opening._courier(visual, 300, 150, False)
                        finally:
                            visual.close()

    def test_legacy_single_atlas_can_draw_player_and_opening(self):
        original = Path(player_visual.METADATA_PATH)
        metadata = json.loads(original.read_text(encoding="utf-8"))
        legacy = {
            "image": str(original.parent / metadata["image"]),
            "canvas_size": metadata["canvas_size"],
            "display_height": metadata["display_height"],
            "frames": {"front_right": [
                {"clip_topleft": [0, 0, 80, 80], "foot_pivot_topleft": [40, 72]},
                {"clip_topleft": [80, 0, 80, 80], "foot_pivot_topleft": [120, 72]},
            ]},
        }
        with tempfile.TemporaryDirectory(prefix="dead-route-legacy-atlas-") as directory:
            path = Path(directory) / "player.json"
            path.write_text(json.dumps(legacy), encoding="utf-8")
            with dummy_canvas(), patch.object(player_visual, "METADATA_PATH", path):
                visual = player_visual.PlayerVisual()
                try:
                    self.assertEqual(list(visual.images), ["atlas"])
                    visual.draw(300, 150)
                    opening._courier(visual, 300, 150, False)
                finally:
                    visual.close()

    def test_close_releases_each_source_once_and_loads_no_font(self):
        visual = None
        with dummy_canvas(), track_texture_destruction() as destroyed:
            with patch.object(p, "TTF_OpenFont", wraps=p.TTF_OpenFont) as font_loads:
                try:
                    visual = player_visual.PlayerVisual()
                    handles = {address(image.texture) for image in visual.images.values()}
                    self.assertEqual(len(handles), len(active_sources(visual.metadata)))
                    visual.close()
                    gc.collect()
                    self.assertFalse(visual.images)
                    self.assertEqual(set(destroyed), handles)
                    self.assertEqual(dict(destroyed), {handle: 1 for handle in handles})
                    visual.close()
                    gc.collect()
                    self.assertEqual(dict(destroyed), {handle: 1 for handle in handles})
                    font_loads.assert_not_called()
                finally:
                    if visual is not None:
                        visual.close()

    def test_bad_middle_canvas_releases_already_loaded_sources(self):
        original_metadata = Path(player_visual.METADATA_PATH)
        metadata = json.loads(original_metadata.read_text(encoding="utf-8"))
        for source in metadata["sources"].values():
            source["image"] = str((original_metadata.parent / source["image"]).resolve())
        metadata["image"] = str((original_metadata.parent / metadata["image"]).resolve())
        order = active_sources(metadata)
        failure_index = len(order) // 2
        metadata["sources"][order[failure_index]]["canvas_size"] = [1, 1]
        loaded = []
        original_load = p.load_image

        def load_image(*args, **kwargs):
            image = original_load(*args, **kwargs)
            loaded.append(address(image.texture))
            return image

        with tempfile.TemporaryDirectory(prefix="dead-route-source-check-") as directory:
            path = Path(directory) / "bad-source.json"
            path.write_text(json.dumps(metadata), encoding="utf-8")
            with dummy_canvas(), track_texture_destruction() as destroyed:
                with patch.object(player_visual, "METADATA_PATH", path), patch.object(
                    p, "load_image", side_effect=load_image
                ):
                    with self.assertRaises(ValueError):
                        player_visual.PlayerVisual()
                    gc.collect()
                    self.assertEqual(len(loaded), failure_index + 1,
                                     "The middle source must reach size validation")
                    self.assertEqual(len(set(loaded)), len(loaded))
                    self.assertEqual(set(destroyed), set(loaded))
                    self.assertTrue(all(destroyed[handle] == 1 for handle in loaded))

    def test_middle_load_failure_releases_loaded_prefix(self):
        original_load = p.load_image
        metadata = json.loads(Path(player_visual.METADATA_PATH).read_text(encoding="utf-8"))
        failure_attempt = len(active_sources(metadata)) // 2 + 1
        loaded, attempts = [], []
        failure = RuntimeError("middle source load failure sentinel")

        def load_image(path):
            attempts.append(path)
            if len(attempts) == failure_attempt:
                raise failure
            image = original_load(path)
            loaded.append(address(image.texture))
            return image

        with dummy_canvas(), track_texture_destruction() as destroyed:
            with patch.object(p, "load_image", side_effect=load_image):
                with self.assertRaises(RuntimeError) as raised:
                    player_visual.PlayerVisual()
                self.assertIs(raised.exception, failure)
                gc.collect()
                self.assertEqual(len(attempts), failure_attempt)
                self.assertEqual(len(loaded), failure_attempt - 1)
                self.assertEqual(set(destroyed), set(loaded))
                self.assertTrue(all(destroyed[handle] == 1 for handle in loaded))


if __name__ == "__main__":
    unittest.main()
