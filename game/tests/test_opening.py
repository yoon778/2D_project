"""Opening and music wiring through the real SDL event and render loop."""
from contextlib import ExitStack
import ctypes
from itertools import count
import math
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main
import pico2d.pico2d as p


class OpeningTests(unittest.TestCase):
    def play(self, batches, *, clock=None, dead=False, smoke=False):
        opening_times, game, worlds, cleanup = [], [], [], []
        music = Mock()
        music.close.side_effect = lambda: cleanup.append("music")
        factory = Mock(return_value=music)
        original_opening, original_draw = main.opening.draw, main.Renderer.draw
        original_world, original_poll, original_close = main.CombatWorld, main.poll_events, p.close_canvas
        original_init = main.Renderer.__init__
        batches = iter(batches)
        ticks = clock if clock is not None else (i / 60 for i in count())

        def initialize(renderer):
            original_init(renderer)
            p.SDL_FlushEvents(p.SDL_FIRSTEVENT, p.SDL_LASTEVENT)

        def poll():
            for kind, *args in next(batches, (("quit",),)):
                event = p.SDL_Event()
                if kind == "key":
                    event.type = p.SDL_KEYDOWN
                    event.key.keysym.sym = args[0]
                elif kind == "click":
                    event.type = p.SDL_MOUSEBUTTONDOWN
                    event.button.button = p.SDL_BUTTON_LEFT
                    event.button.x, event.button.y = (760, 569)
                elif kind == "lost":
                    event.type = p.SDL_WINDOWEVENT
                    event.window.event = p.SDL_WINDOWEVENT_FOCUS_LOST
                elif kind == "quit":
                    event.type = p.SDL_QUIT
                else:
                    raise AssertionError(kind)
                self.assertEqual(p.SDL_PushEvent(ctypes.byref(event)), 1)
            return original_poll()

        def draw_opening(elapsed, *args):
            self.assertFalse(worlds, "The world must wait until opening ends")
            opening_times.append(elapsed)
            original_opening(elapsed, *args)

        def make_world():
            world = original_world()
            if dead:
                world.zombie.hp = 0
            worlds.append(world)
            return world

        def draw(renderer, player, walls, target, focused=True):
            original_draw(renderer, player, walls, target, focused)
            world = renderer.combat
            game.append((player.x, player.y, world.attack is not None, world.zombie.x, world.zombie.y))

        def close():
            cleanup.append("canvas")
            original_close()

        with ExitStack() as patches:
            patches.enter_context(patch.dict("os.environ", {
                "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy", "SDL_RENDER_DRIVER": "software",
            }))
            patches.enter_context(patch.dict(sys.modules, {"spatial_audio": SimpleNamespace(BackgroundMusic=factory)}))
            patches.enter_context(patch.object(p, "SDL_GetWindowFlags", return_value=p.SDL_WINDOW_INPUT_FOCUS))
            patches.enter_context(patch.object(p, "close_canvas", close))
            patches.enter_context(patch.object(main.time, "perf_counter", side_effect=iter(ticks)))
            patches.enter_context(patch.object(main, "poll_events", poll))
            patches.enter_context(patch.object(main, "CombatWorld", side_effect=make_world))
            patches.enter_context(patch.object(main, "capture"))
            patches.enter_context(patch.object(main.Renderer, "__init__", initialize))
            patches.enter_context(patch.object(main.Renderer, "draw", draw))
            patches.enter_context(patch.object(main.opening, "draw", draw_opening))
            main.run(smoke_test=smoke, show_opening=True)
        self.assertEqual(cleanup, ["canvas"] if smoke else ["music", "canvas"])
        if smoke:
            factory.assert_not_called()
        else:
            factory.assert_called_once_with(main.BASE_DIR / "assets/audio/last-delivery.mp3")
            music.start.assert_called_once_with()
            music.close.assert_called_once_with()
        return opening_times, game, worlds, music.update.call_args_list

    def test_three_cuts_end_at_eight_seconds_and_drain_the_transition_batch(self):
        opening, game, worlds, music = self.play(
            [[("key", p.SDLK_w), ("click",)], [("lost",)], [], [], [],
             [("key", p.SDLK_d), ("click",)], [], [("quit",)]],
            clock=[0, 0, 2.6, 3.5, 5.2, 7.99, 8.0, 8.0, 8.02, 8.04],
        )
        self.assertEqual(opening, [0, 2.6, 3.5, 5.2, 7.99])
        self.assertEqual(len(worlds), 1)
        self.assertEqual(len(game), 1)
        self.assertEqual(game[0][:3], (480, 180, False))
        self.assertEqual([call.kwargs for call in music[:5]], [
            {"opening": True, "focused": focused} for focused in (True, False, True, True, True)
        ])
        x, y, _, zx, zy = game[0]
        self.assertEqual(music[-1].kwargs, {"distance": math.hypot(zx - x, zy - y), "focused": True})

    def test_both_enter_keys_skip_and_r_restarts_only_the_game(self):
        for key in (p.SDLK_RETURN, p.SDLK_KP_ENTER):
            with self.subTest(key=key):
                opening, game, worlds, music = self.play([
                    [("key", p.SDLK_w), ("click",), ("key", key), ("key", p.SDLK_a), ("click",)],
                    [], [("key", p.SDLK_d), ("click",)], [("key", p.SDLK_r)], [("quit",)],
                ])
                self.assertFalse(opening)
                self.assertEqual(len(worlds), 1)
                self.assertEqual(game[0][:3], (480, 180, False))
                self.assertEqual(game[1][0], 480)
                self.assertTrue(game[1][2])
                self.assertEqual(game[2][:3], (480, 180, False))
                self.assertTrue(all(not call.kwargs.get("opening") for call in music))

    def test_escape_or_quit_exits_even_when_enter_was_queued_first(self):
        for stop in (("key", p.SDLK_ESCAPE), ("quit",)):
            with self.subTest(stop=stop):
                opening, game, worlds, _ = self.play([[("key", p.SDLK_RETURN), stop]])
                self.assertEqual((opening, game, worlds), ([], [], []))

    def test_dead_zombie_omits_distance_and_lost_focus_pauses_music(self):
        _, game, _, music = self.play([
            [("key", p.SDLK_RETURN)], [("lost",)], [("quit",)],
        ], dead=True)
        self.assertEqual(len(game), 1)
        self.assertEqual(music[0].kwargs, {"distance": None, "focused": False})

    def test_smoke_stays_on_the_three_game_fixtures(self):
        opening, game, worlds, music = self.play([[], [], []], smoke=True)
        self.assertFalse(opening)
        self.assertEqual([frame[1] for frame in game], [180, 420, 300])
        self.assertEqual(len(worlds), 1)
        self.assertFalse(music)


if __name__ == "__main__":
    unittest.main()
