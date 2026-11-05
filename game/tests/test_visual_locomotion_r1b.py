"""Observe real main.run displacement-to-animation wiring using SDL dummy."""
from contextlib import redirect_stdout
import io
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


TEST_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(TEST_DIR.parent))

import main
import pico2d.pico2d as p
from core import Player
import test_visual_input_r1a as input_regression


class LocomotionLoopTests(unittest.TestCase):
    def _run_observed(self, initial, after_draw=None, *, smoke_test=False,
                      player_start=None, maximum_draws=6):
        updates = []
        original_update = main.PlayerVisual.update
        original_run = main.run

        def update(visual, aim_angle, dx, dy):
            original_update(visual, aim_angle, dx, dy)
            locomotion = visual.locomotion
            updates.append({
                "aim_angle": aim_angle, "dx": dx, "dy": dy,
                "facing": locomotion.facing, "moving": locomotion.moving,
                "frame_index": visual.frame_index,
                "frame_count": len(visual.metadata["frames"][locomotion.facing]) - 1,
            })

        def run(*args, **kwargs):
            return original_run(smoke_test=smoke_test)

        def make_player():
            return Player(**(player_start or {}))

        with (
            patch.object(main.PlayerVisual, "update", update),
            patch.object(main, "run", side_effect=run),
            patch.object(main, "Player", side_effect=make_player),
            # Smoke uses its real loop/teleports but never writes screenshot files.
            patch.object(main, "capture", side_effect=lambda path: None) as capture,
            redirect_stdout(io.StringIO()),
        ):
            frames = input_regression.DummyInputTests._run_events(
                self, initial, after_draw, maximum_draws=maximum_draws)

        self.assertEqual(len(updates), len(frames), "One visual update per drawn frame required")
        if smoke_test:
            self.assertEqual(capture.call_count, len(frames))
        else:
            capture.assert_not_called()
        for state, frame in zip(updates, frames):
            self.assertAlmostEqual(state["aim_angle"], frame["aim_angle"], places=9)
            if state["moving"]:
                self.assertLessEqual(1, state["frame_index"])
                self.assertLessEqual(state["frame_index"], state["frame_count"])
            else:
                self.assertEqual(state["frame_index"], 0)
        return frames, updates

    def _assert_actual_displacements(self, frames, updates, start=(480.0, 180.0)):
        before_x, before_y = start
        for frame, update in zip(frames, updates):
            self.assertAlmostEqual(update["dx"], frame["x"] - before_x, places=9)
            self.assertAlmostEqual(update["dy"], frame["y"] - before_y, places=9)
            before_x, before_y = frame["x"], frame["y"]

    def test_held_movement_reaches_update_and_keyup_returns_to_idle(self):
        frames, updates = self._run_observed(
            initial=[("down", p.SDLK_w)],
            after_draw={2: [("up", p.SDLK_w)], 4: [("quit",)]},
        )
        self._assert_actual_displacements(frames, updates)
        self.assertEqual([state["moving"] for state in updates], [True, True, False, False])
        self.assertTrue(all(state["dy"] > 0 for state in updates[:2]))
        self.assertTrue(all(1 <= state["frame_index"] <= state["frame_count"]
                            for state in updates[:2]))
        for state in updates[2:]:
            self.assertEqual((state["dx"], state["dy"], state["frame_index"]), (0.0, 0.0, 0))

    def test_same_batch_focus_loss_gain_sends_zero_displacement_and_idle(self):
        frames, updates = self._run_observed(
            initial=[("down", p.SDLK_w)],
            after_draw={1: [("lost",), ("gained",)], 3: [("quit",)]},
        )
        self._assert_actual_displacements(frames, updates)
        self.assertTrue(updates[0]["moving"])
        for state in updates[1:]:
            self.assertEqual((state["dx"], state["dy"]), (0.0, 0.0))
            self.assertFalse(state["moving"])
            self.assertEqual(state["frame_index"], 0)

    def test_wall_contact_sends_actual_zero_delta_despite_held_input(self):
        frames, updates = self._run_observed(
            initial=[("down", p.SDLK_w)],
            after_draw={2: [("quit",)]},
            player_start={"x": 480.0, "y": 316.0},
        )
        self._assert_actual_displacements(frames, updates, start=(480.0, 316.0))
        for state in updates:
            self.assertEqual((state["dx"], state["dy"]), (0.0, 0.0))
            self.assertFalse(state["moving"])
            self.assertEqual(state["frame_index"], 0)

    def test_raw_mouse_aim_changes_facing_without_quantizing_ground_aim(self):
        frames, updates = self._run_observed(
            initial=[],
            after_draw={1: [("motion", 160, 521)], 2: [("quit",)]},
        )
        self._assert_actual_displacements(frames, updates)
        self.assertEqual([state["facing"] for state in updates], ["back_right", "left"])
        self.assertAlmostEqual(frames[1]["aim_angle"], math.pi, places=9)
        self.assertNotAlmostEqual(frames[1]["aim_angle"], 3 * math.pi / 4, places=5)
        self.assertTrue(all(state["frame_index"] == 0 for state in updates))

    def test_backward_and_strafe_keep_aim_facing_and_send_real_axes(self):
        frames, updates = self._run_observed(
            initial=[("motion", 1120, 521), ("down", p.SDLK_a)],
            after_draw={
                1: [("up", p.SDLK_a), ("down", p.SDLK_w)],
                2: [("up", p.SDLK_w)],
                3: [("quit",)],
            },
        )
        self._assert_actual_displacements(frames, updates)
        self.assertLess(updates[0]["dx"], 0)
        self.assertEqual(updates[0]["dy"], 0)
        self.assertEqual(updates[1]["dx"], 0)
        self.assertGreater(updates[1]["dy"], 0)
        self.assertEqual([state["facing"] for state in updates], ["right"] * 3)
        self.assertEqual([state["moving"] for state in updates], [True, True, False])
        self.assertNotAlmostEqual(frames[1]["aim_angle"], 0.0, places=5)

    def test_smoke_fixture_teleports_do_not_advance_locomotion(self):
        frames, updates = self._run_observed(initial=[], smoke_test=True, maximum_draws=4)
        self.assertEqual([frame["y"] for frame in frames], [180, 420, 300])
        for state in updates:
            self.assertEqual((state["dx"], state["dy"]), (0.0, 0.0))
            self.assertFalse(state["moving"])
            self.assertEqual(state["frame_index"], 0)

    def test_eight_frame_facings_return_to_idle_after_actual_movement(self):
        cases = (
            ("front_right", [("motion", 820, 629)]),
            ("back_right", []),  # Default target keeps the +pi/4 representative.
            ("back_left", [("motion", 460, 413)]),  # Ground target (300, 360).
            ("front_left", [("motion", 460, 629)]),  # Ground target (300, 0).
            ("right", [("motion", 1120, 521)]),  # Ground target (960, 180).
            ("back", [("motion", 640, 269)]),  # Ground target (480, 600).
            ("left", [("motion", 160, 521)]),  # Ground target (0, 180).
            ("front", [("motion", 640, 629)]),  # Ground target (480, 0).
        )
        for facing, aim_events in cases:
            with self.subTest(facing=facing):
                frames, updates = self._run_observed(
                    initial=aim_events + [("down", p.SDLK_w)],
                    after_draw={44: [("up", p.SDLK_w)], 45: [("quit",)]},
                    maximum_draws=46,
                )
                self._assert_actual_displacements(frames, updates)
                moving = updates[:44]
                self.assertEqual(len(updates), 45)
                self.assertTrue(all(state["facing"] == facing for state in updates))
                self.assertTrue(all(state["frame_count"] == 8 for state in updates))
                self.assertTrue(all(state["moving"] for state in moving))
                self.assertEqual({state["frame_index"] for state in moving}, set(range(1, 9)))
                self.assertEqual(updates[-1]["frame_index"], 0)
                self.assertFalse(updates[-1]["moving"])


if __name__ == "__main__":
    unittest.main()
