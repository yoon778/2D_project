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
        original_world = main.CombatWorld

        def update(visual, aim_angle, dx, dy, **kwargs):
            original_update(visual, aim_angle, dx, dy, **kwargs)
            locomotion = visual.locomotion
            updates.append({
                "aim_angle": aim_angle, "dx": dx, "dy": dy,
                "facing": locomotion.facing, "moving": locomotion.moving,
                "phase": locomotion.phase,
                "frame_index": visual.frame_index,
                "frame_count": len(visual.metadata["frames"][locomotion.facing]) - 1,
            })

        def run(*args, **kwargs):
            return original_run(smoke_test=smoke_test, practice=True)

        def make_world():
            world = original_world()
            world.player = Player(**(player_start or {}))
            return world

        with (
            patch.object(main.PlayerVisual, "update", update),
            patch.object(main, "run", side_effect=run),
            patch.object(main, "CombatWorld", side_effect=make_world),
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
            after_draw={1: [("motion", 160, 533)], 26: [("quit",)]},
            maximum_draws=27,
        )
        self._assert_actual_displacements(frames, updates)
        facings = list(dict.fromkeys(state["facing"] for state in updates))
        self.assertEqual(facings, ["front_right", "front", "front_left", "left"])
        self.assertAlmostEqual(frames[-1]["aim_angle"], math.atan2(-20, -480), places=9)
        self.assertTrue(all(state["frame_index"] == 0 for state in updates))

    def test_backward_reverses_walk_then_strafe_and_forward_continue_from_phase(self):
        frames, updates = self._run_observed(
            initial=[("motion", 1120, 521)],
            after_draw={
                6: [("down", p.SDLK_a)],
                17: [("up", p.SDLK_a), ("down", p.SDLK_w)],
                18: [("up", p.SDLK_w), ("down", p.SDLK_d)],
                19: [("up", p.SDLK_d)],
                20: [("down", p.SDLK_a)],
                21: [("quit",)],
            },
            maximum_draws=22,
        )
        self._assert_actual_displacements(frames, updates)
        updates = updates[6:]
        self.assertEqual([state["facing"] for state in updates], ["right"] * 15)
        self.assertEqual([state["frame_index"] for state in updates],
                         [8] * 7 + [7] * 6 + [0, 7])
        self.assertTrue(all(state["dx"] < 0 and state["dy"] == 0 for state in updates[:11]))
        strafe, forward, stopped, restarted = updates[11:]
        self.assertEqual(strafe["dx"], 0)
        self.assertGreater(strafe["dy"], 0)
        self.assertGreater(forward["dx"], 0)
        self.assertEqual((stopped["dx"], stopped["dy"]), (0, 0))
        self.assertLess(restarted["dx"], 0)
        self.assertGreater(strafe["phase"], updates[10]["phase"])
        self.assertGreater(forward["phase"], strafe["phase"])
        self.assertEqual(stopped["phase"], forward["phase"])
        self.assertAlmostEqual(updates[0]["dx"], -65 / 60)
        self.assertAlmostEqual(forward["dx"], 90 / 60)
        self.assertAlmostEqual(restarted["phase"], strafe["phase"] + (90 - 65) / (60 * 64))

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
            ("back_right", [("motion", 820, 413)]),  # Explicit old +pi/4 target.
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
                    initial=aim_events,
                    after_draw={24: [("down", p.SDLK_w)], 85: [("up", p.SDLK_w)], 86: [("quit",)]},
                    maximum_draws=87,
                )
                self._assert_actual_displacements(frames, updates)
                updates = updates[24:]
                moving = updates[:-1]
                self.assertEqual(len(updates), 62)
                self.assertTrue(all(state["facing"] == facing for state in updates))
                self.assertTrue(all(state["frame_count"] == 8 for state in updates))
                self.assertTrue(all(state["moving"] for state in moving))
                self.assertEqual({state["frame_index"] for state in moving}, set(range(1, 9)))
                self.assertEqual(updates[-1]["frame_index"], 0)
                self.assertFalse(updates[-1]["moving"])


if __name__ == "__main__":
    unittest.main()
