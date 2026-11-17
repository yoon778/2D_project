"""Contract selection through the SDL mouse and keyboard event loop."""
from contextlib import ExitStack
import ctypes
from itertools import count
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main

p = main.p
CARDS = ((200, 209), (200, 316), (200, 423))
DISPATCH = (220, 557)


def key(kind, value):
    event = p.SDL_Event()
    event.type = kind
    event.key.keysym.sym = value
    return event


def tap(*keys):
    return tuple(key(kind, value) for value in keys for kind in (p.SDL_KEYDOWN, p.SDL_KEYUP))


def click(point, *, clicks=1, button=p.SDL_BUTTON_LEFT):
    events = []
    for kind in (p.SDL_MOUSEBUTTONDOWN, p.SDL_MOUSEBUTTONUP):
        event = p.SDL_Event()
        event.type = kind
        event.button.button, event.button.clicks = button, clicks
        event.button.x, event.button.y = point
        events.append(event)
    return tuple(events)


def focus_lost():
    event = p.SDL_Event()
    event.type = p.SDL_WINDOWEVENT
    event.window.event = p.SDL_WINDOWEVENT_FOCUS_LOST
    return event


class ContractSelectionTests(unittest.TestCase):
    def replay(self, batches):
        clock = (i / 20 for i in count())
        batches = iter(batches)
        snapshots = []
        original_poll = main.poll_events

        def poll():
            batch = next(batches, None)
            if batch is None:
                end = p.SDL_Event()
                end.type = p.SDL_QUIT
                batch = (end,)
            for event in batch:
                self.assertEqual(p.SDL_PushEvent(ctypes.byref(event)), 1)
            return original_poll()

        def draw(renderer, player, walls, target, focused):
            world = renderer.delivery
            snapshots.append((
                renderer.choosing_delivery, renderer.delivery_preview, world.contract.number,
                world.mission_phase, world.attack_count, renderer.cursor,
            ))

        with ExitStack() as patches:
            patches.enter_context(patch.dict("os.environ", {
                "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy", "SDL_RENDER_DRIVER": "software",
            }))
            audio = SimpleNamespace(BackgroundMusic=Mock())
            patches.enter_context(patch.dict(sys.modules, {"spatial_audio": audio}))
            patches.enter_context(patch.object(main, "ZombieAudio", return_value=Mock()))
            patches.enter_context(patch.object(main.opening, "CutsceneArt", return_value=Mock()))
            patches.enter_context(patch.object(main, "poll_events", poll))
            patches.enter_context(patch.object(main, "current_cursor", return_value=None))
            patches.enter_context(patch.object(main.time, "perf_counter", side_effect=clock))
            patches.enter_context(patch.object(main.Renderer, "draw", draw))
            patches.enter_context(patch.object(p, "SDL_GetWindowFlags", return_value=p.SDL_WINDOW_INPUT_FOCUS))
            main.run()
        return snapshots

    def test_only_new_districts_and_shop_are_selectable(self):
        frames = self.replay([
            tap(p.SDLK_3), tap(p.SDLK_2), tap(p.SDLK_KP_4), tap(p.SDLK_KP_3),
            click(CARDS[0]), click(CARDS[1], button=p.SDL_BUTTON_RIGHT), click(CARDS[1]),
            (*click(DISPATCH), focus_lost()), click(DISPATCH),
            tap(p.SDLK_KP_ENTER), tap(p.SDLK_r), tap(p.SDLK_RETURN),
            click(CARDS[2]), click(DISPATCH),
        ])
        self.assertEqual([frame[1] for frame in frames[:8]], [0, 1, 2, 2, 0, 0, 1, 1])
        self.assertTrue(all(frame[0] for frame in frames[:8]))
        self.assertEqual(frames[8][:5], (False, 1, 2, "arriving", 0))
        self.assertEqual(frames[9][:5], (False, 1, 2, "unloading", 0))
        self.assertTrue(frames[11][0])
        self.assertEqual(frames[-1][:5], (False, 2, 4, "arriving", 0))

    def test_dispatch_input_stays_out_of_the_first_delivery_frame(self):
        frames = self.replay([
            (*tap(p.SDLK_RETURN), key(p.SDL_KEYDOWN, p.SDLK_e), *click(DISPATCH)),
            tap(p.SDLK_KP_ENTER),
            (*click(DISPATCH, clicks=2), key(p.SDL_KEYDOWN, p.SDLK_e)),
            *[()] * 11,
            (key(p.SDL_KEYUP, p.SDLK_e), key(p.SDL_KEYDOWN, p.SDLK_e)),
            *[()] * 10,
            (key(p.SDL_KEYUP, p.SDLK_e), *click((900, 256))),
        ])
        self.assertEqual(frames[0][:5], (False, 0, 1, "arriving", 0))
        self.assertTrue(all(frame[3:5] == ("unloading", 0) for frame in frames[1:14]))
        self.assertEqual(frames[-1][3:5], ("delivering", 1))
