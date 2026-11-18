"""Verify SDL desktop fullscreen, aspect ratio, and scaled pointer events."""
import ctypes
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pico2d.pico2d as p

import display
import main
from contract_selection import contract_card_at


SHELTER_CARD_POINT = (230, 363)


class FullscreenTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy",
                                     SDL_RENDER_DRIVER="software"))
        if p.SDL_WasInit(p.SDL_INIT_VIDEO):
            self.assertEqual(p.SDL_GetCurrentVideoDriver(), b"dummy")
        self.addCleanup(p.close_canvas)
        p.open_canvas(1280, 720)
        self.addCleanup(display.close)
        self.assertEqual(p.SDL_GetCurrentVideoDriver(), b"dummy")
        self.assertTrue(p.renderer, p.SDL_GetError())

    def test_fullscreen_uses_desktop_mode_and_keeps_canvas_coordinates(self):
        monitor = p.SDL_GetWindowDisplayIndex(p.window)
        before, after = p.SDL_DisplayMode(), p.SDL_DisplayMode()
        self.assertEqual(p.SDL_GetCurrentDisplayMode(monitor, ctypes.byref(before)), 0)

        display.configure(fullscreen=True)

        fullscreen = p.SDL_WINDOW_FULLSCREEN_DESKTOP
        self.assertEqual(p.SDL_GetWindowFlags(p.window) & fullscreen, fullscreen)
        self.assertEqual(p.SDL_GetCurrentDisplayMode(monitor, ctypes.byref(after)), 0)
        self.assertEqual((after.w, after.h), (before.w, before.h))
        width, height = ctypes.c_int(), ctypes.c_int()
        p.SDL_RenderGetLogicalSize(p.renderer, ctypes.byref(width), ctypes.byref(height))
        self.assertEqual((width.value, height.value), (1280, 720))

    def test_resized_viewports_letterbox_and_preserve_contract_clicks(self):
        display.configure(fullscreen=False)
        for width, height in ((1600, 900), (960, 600), (2560, 1080), (900, 1200)):
            with self.subTest(output=(width, height)):
                p.SDL_SetWindowSize(p.window, width, height)
                p.SDL_PumpEvents()
                xscale, yscale = ctypes.c_float(), ctypes.c_float()
                p.SDL_RenderGetScale(p.renderer, ctypes.byref(xscale), ctypes.byref(yscale))
                self.assertAlmostEqual(xscale.value, min(width / 1280, height / 720), places=5)
                self.assertAlmostEqual(xscale.value, yscale.value)

                x, y = ctypes.c_int(), ctypes.c_int()
                logical_x, logical_y = SHELTER_CARD_POINT
                p.SDL_RenderLogicalToWindow(p.renderer, logical_x, logical_y, ctypes.byref(x), ctypes.byref(y))
                click = self.push_pointer(p.SDL_MOUSEBUTTONDOWN, x.value, y.value)
                self.assertEqual(contract_card_at(*display.cursor_in_canvas(*click)), 2)
                self.assertAlmostEqual(click[0], logical_x, delta=2)
                self.assertAlmostEqual(click[1], logical_y, delta=2)

                has_bars = width * 720 != height * 1280
                motion = self.push_pointer(p.SDL_MOUSEMOTION, 0, 0)
                self.assertEqual(display.cursor_in_canvas(*motion), None if has_bars else (0, 0))

                samples = self.render_pixels(
                    lambda: display.clear((36, 50, 63)),
                    p.SDL_Rect(width // 2, height // 2, 1, 1), p.SDL_Rect(0, 0, 1, 1))
                self.assertEqual(samples, [[0xFF24323F], [0xFF000000 if has_bars else 0xFF24323F]])
                self.assertEqual(self.read_cursor_at(x.value, y.value), click)
                self.assertEqual(self.read_cursor_at(0, 0), None if has_bars else (0, 0))

    def test_integer_pixels_center_at_1080p_double_at_1440p_and_fit_small_output(self):
        display.configure(fullscreen=False, integer_scale=True)

        def draw_canvas():
            display.clear((36, 50, 63))
            p.SDL_SetRenderDrawColor(p.renderer, 255, 255, 255, 255)
            p.SDL_RenderDrawPoint(p.renderer, 0, 0)

        for width, height, left, top, scale in (
            (1920, 1080, 320, 180, 1),
            (2560, 1440, 0, 0, 2),
            (960, 540, 0, 0, 0.75),
            (1920, 1080, 320, 180, 1),
        ):
            with self.subTest(output=(width, height)):
                p.SDL_SetWindowSize(p.window, width, height)
                list(main.poll_events())
                right = left + round(1280 * scale)
                bottom = top + round(720 * scale)
                first_pixel = p.SDL_Rect(left, top, 3, 1)
                last_pixel = p.SDL_Rect(right - 1, bottom - 1, 1, 1)
                top_left = p.SDL_Rect(0, 0, 1, 1)
                row, edge, corner = self.render_pixels(draw_canvas, first_pixel, last_pixel, top_left)
                self.assertTrue(display.integer_scale_enabled())
                self.assertEqual(edge, [0xFF24323F])
                if scale >= 1:
                    self.assertEqual(row, [0xFFFFFFFF] * scale + [0xFF24323F] * (3 - scale))
                if left:
                    self.assertEqual(corner, [0xFF000000])
                    self.assertIsNone(self.read_cursor_at(left - 1, top))
                    self.assertIsNone(self.read_cursor_at(right, bottom - 1))
                    for physical, logical in (((left, top), (0, 0)),
                                              ((right - 1, bottom - 1), (1279, 719))):
                        self.assertEqual(self.read_cursor_at(*physical), logical)
                        self.assertEqual(self.push_pointer(p.SDL_MOUSEBUTTONDOWN, *physical), logical)
                x = left + round(SHELTER_CARD_POINT[0] * scale)
                y = top + round(SHELTER_CARD_POINT[1] * scale)
                click = self.push_pointer(p.SDL_MOUSEBUTTONDOWN, x, y)
                self.assertEqual(contract_card_at(*click), 2)
                self.assertEqual(self.read_cursor_at(x, y), click)

        display.set_integer_scale(False)
        self.assertFalse(display.integer_scale_enabled())
        left, right = self.render_pixels(lambda: display.clear((36, 50, 63)),
                                         p.SDL_Rect(0, 0, 1, 1), p.SDL_Rect(1919, 1079, 1, 1))
        self.assertEqual((left, right), ([0xFF24323F], [0xFF24323F]))

    def test_scaled_output_preserves_adjacent_one_pixel_clip_rows(self):
        display.configure(fullscreen=False)

        def draw_light_band():
            display.clear()
            p.SDL_SetRenderDrawColor(p.renderer, 255, 255, 255, 255)
            # Lighting uses adjacent one-pixel-high strips to clip the silhouette.
            for y in range(200, 520):
                clip = p.SDL_Rect(0, y, 1280, 1)
                p.SDL_RenderSetClipRect(p.renderer, ctypes.byref(clip))
                p.SDL_RenderFillRect(p.renderer, None)
            p.SDL_RenderSetClipRect(p.renderer, None)

        for width, height in ((1920, 1080), (960, 540)):
            with self.subTest(output=(width, height)):
                p.SDL_SetWindowSize(p.window, width, height)
                p.SDL_PumpEvents()
                column, = self.render_pixels(draw_light_band, p.SDL_Rect(width // 2, 0, 1, height))
                first, end = 200 * height // 720, 520 * height // 720
                self.assertEqual(column[:first], [0xFF000000] * first)
                self.assertEqual(column[first:end], [0xFFFFFFFF] * (end - first))
                self.assertEqual(column[end:], [0xFF000000] * (height - end))

    def render_pixels(self, draw, *regions):
        samples = []

        def before_present():
            # SDL pixel reads clip to the viewport. Restore the full viewport
            # briefly to sample letterbox bars as well as the image itself.
            width, height = ctypes.c_int(), ctypes.c_int()
            p.SDL_RenderGetLogicalSize(p.renderer, ctypes.byref(width), ctypes.byref(height))
            self.assertEqual(p.SDL_RenderSetLogicalSize(p.renderer, 0, 0), 0)
            try:
                samples.extend(self.pixels(region) for region in regions)
            finally:
                self.assertEqual(p.SDL_RenderSetLogicalSize(p.renderer, width.value, height.value), 0)

        with patch.object(p, "update_canvas", side_effect=before_present) as present:
            with display.frame():
                draw()
            present.assert_called_once()
        return samples

    def push_pointer(self, event_type, x, y):
        event = p.SDL_Event()
        event.type = event_type
        point = event.motion if event_type == p.SDL_MOUSEMOTION else event.button
        point.windowID = p.SDL_GetWindowID(p.window)
        point.x, point.y = x, y
        p.SDL_FlushEvent(event_type)
        self.assertEqual(p.SDL_PushEvent(ctypes.byref(event)), 1)
        self.assertEqual(p.SDL_PeepEvents(ctypes.byref(event), 1, p.SDL_GETEVENT, event_type, event_type), 1)
        return point.x, point.y

    def read_cursor_at(self, x, y):
        def pointer_state(output_x, output_y):
            ctypes.cast(output_x, ctypes.POINTER(ctypes.c_int))[0] = x
            ctypes.cast(output_y, ctypes.POINTER(ctypes.c_int))[0] = y
            return 0

        with (patch.object(p, "SDL_GetMouseFocus", return_value=p.window),
              patch.object(p, "SDL_GetMouseState", side_effect=pointer_state)):
            return main.current_cursor()

    def pixels(self, rect):
        data = (ctypes.c_uint32 * (rect.w * rect.h))()
        self.assertEqual(p.SDL_RenderReadPixels(p.renderer, ctypes.byref(rect), p.SDL_PIXELFORMAT_ARGB8888,
                                                data, rect.w * 4), 0, p.SDL_GetError())
        return list(data)
