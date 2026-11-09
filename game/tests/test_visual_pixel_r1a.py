"""Read actual SDL texture sampling using dummy video/audio only."""
import ctypes
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pico2d.pico2d as p
from player_visual import PlayerVisual


class PixelSamplingTests(unittest.TestCase):
    def test_loaded_player_texture_explicitly_uses_nearest_sampling(self):
        sprite = None
        canvas_open = False
        hint = p.SDL_HINT_RENDER_SCALE_QUALITY
        previous_hint = p.SDL_GetHint(hint)
        with patch.dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy"):
            try:
                if p.SDL_WasInit(p.SDL_INIT_VIDEO):
                    self.assertEqual(p.SDL_GetCurrentVideoDriver(), b"dummy")
                canvas_open = True
                p.open_canvas(1280, 720, sync=False)
                if not p.renderer:
                    p.renderer = p.SDL_CreateRenderer(
                        p.window, -1, p.SDL_RENDERER_SOFTWARE)
                self.assertTrue(p.renderer, p.SDL_GetError())
                self.assertEqual(p.SDL_GetCurrentVideoDriver(), b"dummy")
                # A linear default prevents passing merely because SDL defaults to nearest.
                self.assertTrue(p.SDL_SetHint(hint, b"1"))
                sprite = PlayerVisual()
                frame = sprite.metadata["frames"][sprite.locomotion.facing][0]
                texture = sprite.images[frame.get("source", "atlas")].texture
                sampling = ctypes.c_int(-1)
                result = p.SDL_GetTextureScaleMode(
                    texture, ctypes.byref(sampling))
                self.assertEqual(result, 0, p.SDL_GetError())
                self.assertEqual(sampling.value, p.SDL_ScaleModeNearest)
            finally:
                if sprite is not None:
                    sprite.close()
                if canvas_open:
                    p.close_canvas()
                if previous_hint is None:
                    p.SDL_ResetHint(hint)
                else:
                    p.SDL_SetHint(hint, previous_hint)


if __name__ == "__main__":
    unittest.main()
