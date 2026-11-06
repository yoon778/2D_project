"""Verify title-free raw polling without SDL initialization or a window."""
import ctypes
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main
import pico2d.pico2d as p


GAME_TITLE = b"Dead Route - R2-Z"


class WindowTitleTests(unittest.TestCase):
    def setUp(self):
        self.window = object()
        self.title = GAME_TITLE
        self.observations = []
        self.set_title = Mock(side_effect=self._set_title)
        self.delay = Mock(side_effect=self._delay)
        self.poll = Mock(return_value=0)
        self.get_time = Mock(return_value=10.0)
        self.original_print_fps = p.print_fps
        # Detect and clean up any unexpected vendor callback replacement.
        callback_patch = patch.object(p, "print_fps", self.original_print_fps)
        callback_patch.start()
        self.addCleanup(callback_patch.stop)
        globals_patch = patch.multiple(
            p, window=self.window, canvas_width=1280, canvas_height=720,
            cur_time=0.0, get_time=self.get_time,
            SDL_SetWindowTitle=self.set_title, SDL_Delay=self.delay,
            SDL_PollEvent=self.poll, create=True,
        )
        globals_patch.start()
        self.addCleanup(globals_patch.stop)

    def _set_title(self, window, caption):
        self.assertIs(window, self.window)
        self.title = caption
        self.observations.append(("title", caption))

    def _delay(self, milliseconds):
        self.observations.append(("delay", milliseconds, self.title))

    def test_frame_end_restore_leaves_fps_title_visible_at_polling_delay(self):
        # Real get_events writes the FPS title before its existing SDL_Delay(1).
        self.assertEqual(p.get_events(), [])
        p.SDL_SetWindowTitle(p.window, GAME_TITLE)

        self.assertEqual(self.title, GAME_TITLE)
        delay_observation = next(
            item for item in self.observations if item[0] == "delay"
        )
        self.assertEqual(delay_observation[1], 1)
        self.assertTrue(delay_observation[2].startswith(b"Pico2D Canvas (1280x720)"))
        self.assertIn(b"FPS", delay_observation[2])
        self.assertNotEqual(delay_observation[2], GAME_TITLE)
        self.assertEqual(self.set_title.call_count, 2)
        self.delay.assert_called_once_with(1)
        self.poll.assert_called_once()

    def test_raw_poll_has_no_fps_title_or_vendor_callback_side_effects(self):
        with patch.object(p, "print_fps", wraps=self.original_print_fps) as fps:
            with patch.object(p, "get_events", side_effect=AssertionError("filtered vendor poll used")):
                self.assertEqual(list(main.poll_events()), [])
            fps.assert_not_called()
            self.assertIs(p.print_fps, fps)

        self.delay.assert_not_called()
        self.poll.assert_called_once()
        self.set_title.assert_not_called()
        self.get_time.assert_not_called()
        self.assertEqual(self.observations, [])
        self.assertEqual(self.title, GAME_TITLE)
        self.assertIs(p.print_fps, self.original_print_fps)

    def test_raw_poll_exception_leaves_original_fps_callback_unchanged(self):
        failure = RuntimeError("polling failure sentinel")
        self.poll.side_effect = failure

        with self.assertRaises(RuntimeError) as raised:
            list(main.poll_events())

        self.assertIs(raised.exception, failure)
        self.assertIs(p.print_fps, self.original_print_fps)
        self.delay.assert_not_called()
        self.poll.assert_called_once()
        self.set_title.assert_not_called()

    def test_raw_poll_preserves_key_repeat_and_focus_event_fields(self):
        queued = [
            (p.SDL_KEYDOWN, p.SDLK_w, 1),
            (p.SDL_WINDOWEVENT, p.SDL_WINDOWEVENT_FOCUS_LOST),
            (p.SDL_WINDOWEVENT, p.SDL_WINDOWEVENT_FOCUS_GAINED),
            (p.SDL_QUIT,),
        ]

        def poll(pointer):
            if not queued:
                return 0
            record = queued.pop(0)
            event = ctypes.cast(pointer, ctypes.POINTER(p.SDL_Event)).contents
            event.type = record[0]
            if event.type == p.SDL_KEYDOWN:
                event.key.keysym.sym = record[1]
                event.key.repeat = record[2]
            elif event.type == p.SDL_WINDOWEVENT:
                event.window.event = record[1]
            return 1

        self.poll.side_effect = poll
        observed = []
        # Consume immediately: a raw SDL iterator may reuse its event storage.
        for event in main.poll_events():
            if event.type == p.SDL_KEYDOWN:
                observed.append((event.type, event.key.keysym.sym, event.key.repeat))
            elif event.type == p.SDL_WINDOWEVENT:
                observed.append((event.type, event.window.event))
            else:
                observed.append((event.type,))

        self.assertEqual(observed, [
            (p.SDL_KEYDOWN, p.SDLK_w, 1),
            (p.SDL_WINDOWEVENT, p.SDL_WINDOWEVENT_FOCUS_LOST),
            (p.SDL_WINDOWEVENT, p.SDL_WINDOWEVENT_FOCUS_GAINED),
            (p.SDL_QUIT,),
        ])
        self.delay.assert_not_called()
        self.set_title.assert_not_called()
        self.assertIs(p.print_fps, self.original_print_fps)


if __name__ == "__main__":
    unittest.main()
