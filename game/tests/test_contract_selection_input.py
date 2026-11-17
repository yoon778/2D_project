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
CARDS = ((200, 195), (200, 277), (200, 356), (200, 436))
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
    def replay(self, batches, *, unlocked=False):
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
                renderer.choosing_delivery, renderer.delivery_preview, main.DELIVERY_CONTRACTS.index(world.contract),
                world.mission_phase, world.attack_count, renderer.cursor,
            ))

        with ExitStack() as patches:
            patches.enter_context(patch.dict("os.environ", {
                "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy", "SDL_RENDER_DRIVER": "software",
            }))
            audio = SimpleNamespace(BackgroundMusic=Mock())
            patches.enter_context(patch.dict(sys.modules, {"spatial_audio": audio}))
            patches.enter_context(patch.object(main, "load_two_stop_unlock", return_value=unlocked))
            patches.enter_context(patch.object(main, "ZombieAudio", return_value=Mock()))
            patches.enter_context(patch.object(main.opening, "CutsceneArt", return_value=Mock()))
            patches.enter_context(patch.object(main, "poll_events", poll))
            patches.enter_context(patch.object(main, "current_cursor", return_value=None))
            patches.enter_context(patch.object(main.time, "perf_counter", side_effect=clock))
            patches.enter_context(patch.object(main.Renderer, "draw", draw))
            patches.enter_context(patch.object(p, "SDL_GetWindowFlags", return_value=p.SDL_WINDOW_INPUT_FOCUS))
            main.run()
        return snapshots

    def test_mixed_selection_locked_preview_and_input_isolation(self):
        frames = self.replay([
            tap(p.SDLK_KP_4), click(CARDS[0]), tap(p.SDLK_2), click(CARDS[2]),
            tap(p.SDLK_RETURN), click(DISPATCH), click((900, 256)), click(CARDS[3], clicks=2),
            click(CARDS[3]), (*click(DISPATCH), focus_lost()),
            (*tap(p.SDLK_RETURN), key(p.SDL_KEYDOWN, p.SDLK_e), *click(DISPATCH)),
            tap(p.SDLK_KP_ENTER), tap(p.SDLK_r), tap(p.SDLK_RETURN),
            (*click(CARDS[0]), *click(DISPATCH), key(p.SDL_KEYUP, p.SDLK_e), key(p.SDL_KEYDOWN, p.SDLK_e)),
            (*click(DISPATCH, clicks=2), key(p.SDL_KEYDOWN, p.SDLK_e)),
            *[()] * 11,
            (key(p.SDL_KEYUP, p.SDLK_e), key(p.SDL_KEYDOWN, p.SDLK_e)),
            *[()] * 10,
            (key(p.SDL_KEYUP, p.SDLK_e), *click((900, 256))),
        ])
        self.assertEqual([frame[1] for frame in frames[:10]], [3, 0, 1, 2, 2, 2, 2, 2, 3, 3])
        self.assertTrue(all(frame[0] for frame in frames[:10]))
        self.assertEqual(frames[3][5], CARDS[2])
        self.assertIsNone(frames[9][5])
        self.assertEqual(frames[10][:5], (False, 3, 3, "arriving", 0))
        self.assertEqual(frames[11][:5], (False, 3, 3, "unloading", 0))
        self.assertTrue(frames[13][0])
        self.assertEqual(frames[14][:5], (False, 0, 0, "unloading", 0))
        self.assertTrue(all(frame[3:5] == ("unloading", 0) for frame in frames[15:27]))
        self.assertEqual(frames[-1][3:5], ("delivering", 1))

    def test_saved_unlock_enables_third_card_departure(self):
        frames = self.replay([
            tap(p.SDLK_2), tap(p.SDLK_RETURN), tap(p.SDLK_r), tap(p.SDLK_RETURN),
            click(CARDS[2]), click(CARDS[0], button=p.SDL_BUTTON_RIGHT), click(DISPATCH),
        ], unlocked=True)
        self.assertEqual(frames[1][:5], (False, 1, 1, "unloading", 0))
        self.assertEqual([frame[:2] for frame in frames[-3:]], [(True, 2), (True, 2), (False, 2)])
        self.assertEqual(frames[-1][2:5], (2, "unloading", 0))
