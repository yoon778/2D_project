"""R2-AW selection/anchors and real SDL queue movement-to-sprite integration."""
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

TEST_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(TEST_DIR.parent))

import main
from combat_visual import CombatVisual, METADATA_PATH
import test_combat_visual_r2a as combat_fixture


class AttackWalkSpriteTests(unittest.TestCase):
    def setUp(self):
        self.visual = CombatVisual.__new__(CombatVisual)
        self.visual.metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        self.visual.images = {key: SimpleNamespace(h=self.visual.metadata[key]["canvas_size"][1], clip_draw=Mock())
                              for key in ("attack", "attack_walk", "attack_stationary_front_right")}

    def test_all_96_fr_combinations_choose_the_right_cell_with_the_same_anchor(self):
        self.assertEqual(self.visual.metadata["attack_walk"]["canvas_size"], [768, 1152])
        self.assertEqual(self.visual.metadata["attack_walk"]["attack_steps"], 12)
        self.assertEqual(self.visual.metadata["attack_walk"]["walk_phases"], 8)
        self.assertEqual(len(self.visual.metadata["attack"]["frames"]), 12)
        self.assertEqual(len(self.visual.metadata["attack_walk"]["frames"]), 96)
        for a, pose in enumerate(self.visual.metadata["attack"]["frames"]):
            attack = SimpleNamespace(facing="front_right", elapsed=(pose["start"] + pose["end"]) / 2)
            for w in range(1, 9):
                with self.subTest(attack=a, walk=w):
                    self.assertTrue(self.visual.draw_attack(attack, 100, 200, w))
                    self.visual.images["attack_walk"].clip_draw.assert_called_with(
                        (w - 1) * 96, 1152 - (a + 1) * 96, 96, 96,
                        100.0, 264.0, 192.0, 192.0)
        self.visual.images["attack"].clip_draw.assert_not_called()

    def test_stopping_uses_existing_stationary_attack_and_invalid_phase_is_rejected(self):
        attack = SimpleNamespace(facing="front_right", elapsed=.18)
        for w in (None, 0):
            self.assertTrue(self.visual.draw_attack(attack, 100, 200, w))
        self.assertEqual(self.visual.images["attack"].clip_draw.call_count, 2)
        self.visual.images["attack_walk"].clip_draw.assert_not_called()
        for w in (-1, 9, True, 1.5):
            with self.subTest(walk=w), self.assertRaises(ValueError):
                self.visual.draw_attack(attack, 100, 200, w)
        self.assertFalse(self.visual.draw_attack(None, 100, 200, 8))


    def test_locked_stationary_fr_uses_eight_cells_on_the_same_attack_clock(self):
        source = self.visual.metadata["attack_stationary_front_right"]
        image = self.visual.images["attack_stationary_front_right"]
        self.assertEqual(source["canvas_size"], [768, 96])
        self.assertEqual(source["image"], "r2sf8-arm-attack-front-right.png")
        boundaries = (0, .03, .10, .18, .24, .30, .37, .44, .66)
        self.assertEqual([frame["start"] for frame in source["frames"]], list(boundaries[:-1]))
        self.assertEqual([frame["end"] for frame in source["frames"]], list(boundaries[1:]))
        attack = SimpleNamespace(facing="front_right", stationary_front_right=True, hit_time=.24)
        for index, (start, end) in enumerate(zip(boundaries, boundaries[1:])):
            for elapsed in (start, math.nextafter(end, -math.inf)):
                with self.subTest(index=index, elapsed=elapsed):
                    attack.elapsed = elapsed
                    self.assertEqual(self.visual.attack_frame_index(attack), index)
                    self.assertTrue(self.visual.draw_attack(attack, 100, 200, 0))
                    image.clip_draw.assert_called_with(index * 96, 0, 96, 96,
                                                       100.0, 264.0, 192.0, 192.0)
        attack.elapsed = .66
        self.assertIsNone(self.visual.attack_frame_index(attack))
        self.assertFalse(self.visual.draw_attack(attack, 100, 200, 0))

    def test_locked_fr_uses_legacy_walk_cells_on_the_new_clock(self):
        boundaries = (0, .06, .12, .18, .24, .285, .33, .38, .43, .485, .54, .60, .66)
        attack = SimpleNamespace(facing="front_right", stationary_front_right=True, hit_time=.24)
        image = self.visual.images["attack_walk"]
        for index, (start, end) in enumerate(zip(boundaries, boundaries[1:])):
            for elapsed in (start, math.nextafter(end, -math.inf)):
                for phase in (1, 8):
                    with self.subTest(index=index, elapsed=elapsed, phase=phase):
                        attack.elapsed = elapsed
                        self.assertTrue(self.visual.draw_attack(attack, 100, 200, phase))
                        image.clip_draw.assert_called_with(
                            (phase - 1) * 96, 1152 - (index + 1) * 96, 96, 96,
                            100.0, 264.0, 192.0, 192.0)
        self.visual.images["attack_stationary_front_right"].clip_draw.assert_not_called()
        attack.elapsed = .66
        self.assertFalse(self.visual.draw_attack(attack, 100, 200, 1))

    def test_locked_fr_can_resume_its_stationary_source_but_moving_start_keeps_legacy(self):
        attack = SimpleNamespace(facing="front_right", stationary_front_right=True, hit_time=.24, elapsed=.24)
        self.assertTrue(self.visual.draw_attack(attack, 100, 200, 4))
        self.assertTrue(self.visual.draw_attack(attack, 100, 200, 0))
        self.visual.images["attack_stationary_front_right"].clip_draw.assert_called_once_with(
            384, 0, 96, 96, 100.0, 264.0, 192.0, 192.0)
        attack.stationary_front_right = False
        attack.elapsed = .18
        self.assertTrue(self.visual.draw_attack(attack, 100, 200, 4))
        self.assertTrue(self.visual.draw_attack(attack, 100, 200, 0))
        self.visual.images["attack"].clip_draw.assert_called_once_with(
            0, 96, 96, 96, 100.0, 264.0, 192.0, 192.0)
        self.assertEqual(self.visual.images["attack_stationary_front_right"].clip_draw.call_count, 1)


class AttackWalkInputTests(unittest.TestCase):
    def observe(self, initial, after_draw, maximum_draws=6, phase=0, wall=False):
        choices = []
        original_init, original_draw = main.Renderer.__init__, CombatVisual.draw_attack
        original_world = main.CombatWorld

        def initialize(renderer):
            original_init(renderer)
            renderer.player_visual.locomotion.phase = phase

        def draw(visual, attack, x, y, walk_frame_index=None):
            drawn = original_draw(visual, attack, x, y, walk_frame_index)
            choices.append({"walk": walk_frame_index, "drawn": drawn,
                            "attack_index": visual.attack_frame_index(attack)})
            return drawn

        def make_world():
            world = original_world()
            if wall:
                world.player.y = 316
            return world

        with (patch.object(main.Renderer, "__init__", initialize),
              patch.object(CombatVisual, "draw_attack", draw),
              patch.object(main, "CombatWorld", side_effect=make_world)):
            frames, states = combat_fixture.CombatInputTests.observe(self, initial, after_draw, maximum_draws)
        self.assertEqual(len(choices), len(states))
        for frame, state, choice in zip(frames, states, choices):
            expected = min(8, int(state["phase"] * 8) + 1) if frame["moved"] else 0
            self.assertEqual(choice["walk"], expected)
        return frames, states, choices

    def test_attack_start_and_movement_key_changes_preserve_walk_phase(self):
        _, states, choices = self.observe(
            [("click", 760, 569), ("down", main.p.SDLK_d)],
            {1: [("up", main.p.SDLK_d)], 3: [("down", main.p.SDLK_d)], 4: [("quit",)]}, phase=.37)
        self.assertEqual([c["walk"] for c in choices], [0, 0, 0, 0])
        self.assertEqual([c["drawn"] for c in choices], [True] * 4)
        self.assertTrue(all(state["phase"] == .37 for state in states))

    def test_movement_input_keeps_the_stationary_atlas_on_the_locked_clock(self):
        sources = []
        original = CombatVisual._draw

        def draw(visual, source, frame, *args):
            if source.startswith("attack"):
                sources.append(source)
            return original(visual, source, frame, *args)

        with patch.object(CombatVisual, "_draw", draw):
            _, states, choices = self.observe(
                [("click", 760, 569)],
                {1: [("down", main.p.SDLK_d)], 2: [("up", main.p.SDLK_d)], 3: [("quit",)]},
                phase=.37)
        self.assertTrue(all(state["attack"].stationary_front_right for state in states))
        self.assertEqual([choice["walk"] for choice in choices], [0, 0, 0])
        self.assertEqual(sources, ["attack_stationary_front_right"] * 3)
        self.assertTrue(all(state["phase"] == .37 for state in states))

    def test_wall_contact_selects_stationary_attack_without_changing_phase(self):
        frames, states, choices = self.observe(
            [("click", 760, 569), ("down", main.p.SDLK_w)], {2: [("quit",)]}, phase=.4, wall=True)
        self.assertEqual([f["y"] for f in frames], [316, 316])
        self.assertTrue(all(c["walk"] == 0 and c["drawn"] for c in choices))
        self.assertTrue(all(s["phase"] == .4 for s in states))

    def test_forward_backward_and_strafe_inputs_leave_attack_stationary(self):
        for key in (main.p.SDLK_a, main.p.SDLK_w, main.p.SDLK_d):
            with self.subTest(key=key):
                _, states, choices = self.observe(
                    [("click", 1120, 521), ("down", key)], {2: [("quit",)]})
                self.assertEqual([c["walk"] for c in choices], [0, 0])
                self.assertTrue(all(c["drawn"] for c in choices))
                self.assertEqual(states[1]["phase"], 0)

    def test_attack_end_preserves_phase_and_returns_to_normal_walking(self):
        original_draw = main.PlayerVisual.draw
        for key, direction in ((main.p.SDLK_d, 1), (main.p.SDLK_a, -1)):
            with self.subTest(direction=direction):
                walk_draws = []

                def draw_walk(visual, *args):
                    walk_draws.append(visual.frame_index)
                    return original_draw(visual, *args)

                with patch.object(main.PlayerVisual, "draw", draw_walk):
                    frames, states, choices = self.observe(
                        [("click", 1120, 521), ("down", key)], {40: [("quit",)]}, 41, phase=.2)
                distance = 0.0
                previous = (480, 180)
                for frame, state in zip(frames, states):
                    point = (frame["x"], frame["y"])
                    distance += math.dist(previous, point)
                    self.assertAlmostEqual(state["phase"], (.2 + direction * distance / 64) % 1)
                    previous = point
                self.assertEqual({c["attack_index"] for c in choices if c["attack_index"] is not None}, set(range(12)))
                self.assertIsNone(states[-1]["attack"])
                self.assertFalse(choices[-1]["drawn"])
                self.assertGreater(choices[-1]["walk"], 0)
                self.assertEqual(walk_draws[-1], choices[-1]["walk"])

    def test_focus_pause_and_reset_choose_static_or_normal_without_extra_phase(self):
        _, states, choices = self.observe(
            [("click", 760, 569), ("down", main.p.SDLK_d)],
            {1: [("lost",), ("gained",)], 2: [("down", main.p.SDLK_d)],
             3: [("down", main.p.SDLK_r)], 4: [("quit",)]}, phase=.3)
        self.assertEqual(choices[1]["walk"], 0)
        self.assertEqual(states[0]["elapsed"], states[1]["elapsed"])
        self.assertEqual(states[0]["phase"], states[1]["phase"])
        self.assertEqual(states[2]["phase"], .3)
        self.assertEqual(states[3]["phase"], 0)
        self.assertFalse(choices[3]["drawn"])


if __name__ == "__main__":
    unittest.main()
