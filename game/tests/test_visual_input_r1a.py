"""R1-A run() event-queue regressions under SDL dummy, without native input."""
import ctypes
from dataclasses import asdict
from itertools import count
import math
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main
import pico2d.pico2d as p


class DummyInputTests(unittest.TestCase):
    def _run_events(self, initial, after_draw=None, maximum_draws=6):
        """Replay real queued SDL events while retaining real rendering/cleanup."""
        after_draw = after_draw or {}
        frames = []
        renderers = []
        closed = []
        safety_quits = []
        original_init = main.Renderer.__init__
        original_draw = main.Renderer.draw
        original_close = main.Renderer.close

        def push(specification):
            kind, *values = specification
            event = p.SDL_Event()
            if kind in ("down", "up"):
                event.type = p.SDL_KEYDOWN if kind == "down" else p.SDL_KEYUP
                event.key.type = event.type
                event.key.windowID = p.SDL_GetWindowID(p.window)
                event.key.state = p.SDL_PRESSED if kind == "down" else p.SDL_RELEASED
                event.key.repeat = 0
                event.key.keysym.sym = values[0]
            elif kind in ("lost", "gained"):
                event.type = p.SDL_WINDOWEVENT
                event.window.type = p.SDL_WINDOWEVENT
                event.window.windowID = p.SDL_GetWindowID(p.window)
                event.window.event = (
                    p.SDL_WINDOWEVENT_FOCUS_LOST if kind == "lost"
                    else p.SDL_WINDOWEVENT_FOCUS_GAINED
                )
            elif kind == "motion":
                event.type = p.SDL_MOUSEMOTION
                event.motion.type = p.SDL_MOUSEMOTION
                event.motion.windowID = p.SDL_GetWindowID(p.window)
                event.motion.x, event.motion.y = values
            elif kind == "quit":
                event.type = p.SDL_QUIT
            else:
                raise AssertionError(f"Unknown event specification: {specification!r}")
            pushed = p.SDL_PushEvent(ctypes.byref(event))
            self.assertEqual(pushed, 1, p.SDL_GetError())

        def initialize(renderer):
            original_init(renderer)
            renderers.append(renderer)
            # Ignore the dummy window's startup events, not application frames.
            p.SDL_FlushEvents(p.SDL_FIRSTEVENT, p.SDL_LASTEVENT)
            for specification in initial:
                push(specification)

        def draw(renderer, player, walls, target, focused=True):
            original_draw(renderer, player, walls, target, focused)
            frames.append(asdict(player))
            frames[-1]["_target"] = tuple(target)
            number = len(frames)
            if number > maximum_draws:
                raise AssertionError("Application ignored the bounded safety QUIT")
            for specification in after_draw.get(number, ()):
                push(specification)
            if number == maximum_draws:
                safety_quits.append(number)
                push(("quit",))

        def close(renderer):
            original_close(renderer)
            closed.append(renderer)

        clock = count()
        with (
            patch.dict(os.environ, {
                "SDL_VIDEODRIVER": "dummy",
                "SDL_AUDIODRIVER": "dummy",
                "SDL_RENDER_DRIVER": "software",
            }),
            patch.object(main.time, "perf_counter", side_effect=lambda: next(clock) / 60.0),
            patch.object(p, "SDL_GetWindowFlags", return_value=p.SDL_WINDOW_INPUT_FOCUS),
            patch.object(main.Renderer, "__init__", initialize),
            patch.object(main.Renderer, "draw", draw),
            patch.object(main.Renderer, "close", close),
            patch.object(p, "SDL_SetWindowTitle", wraps=p.SDL_SetWindowTitle) as title_writes,
            patch.object(p, "print_fps", wraps=p.print_fps) as fps_calls,
            patch.object(p, "get_events", wraps=p.get_events) as vendor_event_calls,
        ):
            main.run(smoke_test=False)

        title_writes.assert_called_once_with(p.window, b"Dead Route - R1-B")
        fps_calls.assert_not_called()
        vendor_event_calls.assert_not_called()
        self.assertEqual(len(renderers), 1)
        self.assertEqual(closed, renderers)
        self.assertIsNone(renderers[0].font)
        self.assertIsNone(renderers[0].player_visual)
        self.assertEqual(p.SDL_WasInit(p.SDL_INIT_VIDEO), 0)
        self.assertEqual(p.TTF_WasInit(), 0)
        self.assertFalse(safety_quits, "Case reached its safety bound instead of its intended exit")
        return frames

    def test_focus_lost_and_gained_in_one_batch_clear_held_movement(self):
        frames = self._run_events(
            initial=[("down", p.SDLK_w)],
            after_draw={
                1: [("lost",), ("gained",)],
                3: [("quit",)],
            },
        )
        self.assertEqual(len(frames), 3)
        self.assertGreater(frames[0]["y"], 180.0)
        self.assertAlmostEqual(
            frames[1]["y"], frames[0]["y"], places=7,
            msg="Held W survived FOCUS_LOST+GAINED without a fresh KEYDOWN",
        )
        self.assertAlmostEqual(frames[2]["y"], frames[0]["y"], places=7)
        self.assertFalse(frames[1]["moved"])
        self.assertFalse(frames[2]["moved"])

    def test_held_key_moves_until_keyup_then_stays_stopped(self):
        frames = self._run_events(
            initial=[("down", p.SDLK_w)],
            after_draw={2: [("up", p.SDLK_w)], 4: [("quit",)]},
        )
        self.assertEqual(len(frames), 4)
        for frame in frames:
            self.assertAlmostEqual(frame["x"], 480.0, places=7)
        self.assertAlmostEqual(frames[0]["y"], 181.5, places=7)
        self.assertAlmostEqual(frames[1]["y"], 183.0, places=7)
        self.assertAlmostEqual(frames[2]["y"], frames[1]["y"], places=7)
        self.assertAlmostEqual(frames[3]["y"], frames[1]["y"], places=7)
        self.assertEqual([frame["moved"] for frame in frames], [True, True, False, False])

    def test_same_batch_down_up_tap_has_no_held_movement(self):
        frames = self._run_events(
            initial=[("down", p.SDLK_w), ("up", p.SDLK_w)],
            after_draw={1: [("quit",)]},
        )
        self.assertEqual(len(frames), 1)
        self.assertAlmostEqual(frames[0]["x"], 480.0, places=7)
        self.assertAlmostEqual(frames[0]["y"], 180.0, places=7)
        self.assertFalse(frames[0]["moved"])

    def test_raw_mouse_motion_changes_ground_aim_without_moving_player(self):
        frames = self._run_events(
            initial=[],
            after_draw={1: [("motion", 160, 521)], 2: [("quit",)]},
        )
        self.assertEqual(len(frames), 2)
        self.assertEqual(frames[0]["_target"], (660.0, 360.0))
        self.assertEqual(frames[1]["_target"], (0.0, 180.0))
        self.assertAlmostEqual(frames[0]["aim_angle"], math.pi / 4, places=7)
        self.assertAlmostEqual(frames[1]["aim_angle"], math.pi, places=7)
        for frame in frames:
            self.assertAlmostEqual(frame["x"], 480.0, places=7)
            self.assertAlmostEqual(frame["y"], 180.0, places=7)
            self.assertFalse(frame["moved"])

    def test_escape_exits_and_releases_real_renderer_resources(self):
        self.assertEqual(self._run_events(initial=[("down", p.SDLK_ESCAPE)]), [])

    def test_quit_exits_and_releases_real_renderer_resources(self):
        self.assertEqual(self._run_events(initial=[("quit",)]), [])


if __name__ == "__main__":
    unittest.main()
