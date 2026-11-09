"""R2-ZA attack-source selection, locked poses/masks and real SDL queue regressions."""
import math
import json
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

TEST_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(TEST_DIR.parent))

from combat import CombatWorld, STUN_DURATION, ZombieAttack
from combat_visual import CombatVisual
import test_zombie_visual_r2z as zombie_fixture


class ZombieAttackSpriteTests(unittest.TestCase):
    def setUp(self):
        self.visual = CombatVisual.__new__(CombatVisual)
        self.visual.metadata = {"zombie": zombie_fixture.zombie_metadata(),
                                "zombie_attack": zombie_fixture.zombie_attack_metadata()}
        self.visual.images = {"zombie": SimpleNamespace(h=1120, clip_draw=Mock()),
                              "zombie_attack": SimpleNamespace(h=960, clip_draw=Mock())}
        self.visual.reset_zombie_animation()

    def test_all_96_locked_attack_poses_use_attack_texture_anchor_and_current_mask(self):
        zombie = CombatWorld().zombie
        for col, (facing, angle) in enumerate(zombie_fixture.FACINGS):
            for index, start in enumerate(zombie_fixture.ATTACK_BOUNDS[:-1]):
                with self.subTest(facing=facing, stage=index):
                    zombie.attack = ZombieAttack(angle, facing, start)
                    zombie.aim_angle = angle + math.pi  # Cursor/target changes cannot rotate an active pose.
                    self.visual.zombie_locomotion.phase = .37
                    self.visual.update_zombie(zombie, 0, 0)
                    frame = self.visual.metadata["zombie_attack"]["facings"][facing][index]
                    self.assertEqual(self.visual._zombie_pose(zombie), ("zombie_attack", frame))
                    self.assertEqual(self.visual.zombie_locomotion.facing, facing)
                    self.assertEqual(self.visual.zombie_locomotion.phase, .37)
                    self.assertFalse(self.visual.zombie_locomotion.moving)
                    self.visual.draw_zombie(zombie, 100, 200)
                    self.visual.images["zombie_attack"].clip_draw.assert_called_with(
                        col * 80, 960 - (index + 1) * 80, 80, 80, 100.0, 264.0, 160.0, 160.0)
                    row = 50 + index
                    screen = (20 + (20 + col * 5 + .5) * 2, 184 + (80 - row - .5) * 2)
                    self.assertTrue(self.visual.zombie_contains(zombie, 100, 200, *screen))
                    self.assertFalse(self.visual.zombie_contains(zombie, 100, 200, screen[0] + 8, screen[1]))
                    self.assertFalse(self.visual.zombie_contains(zombie, 100, 200, 20 + (10 + col * 5 + .5) * 2, 323))
                    zombie.attack.elapsed = math.nextafter(zombie_fixture.ATTACK_BOUNDS[index + 1], -math.inf)
                    self.assertIs(self.visual._zombie_frame(zombie), frame)
        self.visual.images["zombie"].clip_draw.assert_not_called()

    def test_actual_twelve_pose_metadata_matches_boundaries_canvas_and_cell_pivots(self):
        source = json.loads(zombie_fixture.combat_visual.ZOMBIE_ATTACK_METADATA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(source["canvas_size"], [640, 960])
        self.assertEqual(set(source["facings"]), {name for name, _ in zombie_fixture.FACINGS})
        for col, (facing, _) in enumerate(zombie_fixture.FACINGS):
            frames = source["facings"][facing]
            self.assertEqual([frame["start"] for frame in frames], list(zombie_fixture.ATTACK_BOUNDS[:-1]))
            self.assertEqual([frame["end"] for frame in frames], list(zombie_fixture.ATTACK_BOUNDS[1:]))
            for row, frame in enumerate(frames):
                self.assertEqual(frame["clip_topleft"], [col * 80, row * 80, 80, 80])
                self.assertEqual(frame["foot_pivot_topleft"], [col * 80 + 40, row * 80 + 72])
                self.assertTrue(frame["opaque_rows"])

    def test_death_hit_attack_priority_and_recovery_keep_walk_phase_without_loading(self):
        zombie = CombatWorld().zombie
        zombie.aim_angle = -math.pi / 4
        zombie.attack = ZombieAttack(zombie.aim_angle, "front_right", .3)
        self.visual.zombie_locomotion.phase = .37
        self.visual.update_zombie(zombie, 0, 0)
        self.assertEqual(self.visual._zombie_pose(zombie)[0], "zombie_attack")
        zombie.stun_remaining = STUN_DURATION
        self.assertEqual(self.visual._zombie_pose(zombie),
                         ("zombie", self.visual.metadata["zombie"]["facings"]["front_right"]["hit"][0]))
        zombie.hp = 0
        self.assertEqual(self.visual._zombie_pose(zombie), ("zombie", self.visual.metadata["zombie"]["frames"]["dead"]))
        self.assertFalse(self.visual.zombie_contains(zombie, 100, 200, 100, 200))
        zombie.hp, zombie.stun_remaining, zombie.attack = 5, 0, None
        self.visual.update_zombie(zombie, 4, 0)
        self.assertAlmostEqual(self.visual.zombie_locomotion.phase, .37 + 4 / 64)
        self.assertEqual(self.visual._zombie_pose(zombie),
                         ("zombie", self.visual.metadata["zombie"]["facings"]["front_right"]["walk"][3]))
        with patch("combat_visual.p.load_image") as load:
            self.visual.reset_zombie_animation()
            self.visual.draw_zombie(zombie, 100, 200)
            load.assert_not_called()
        self.assertEqual(self.visual.zombie_locomotion.phase, 0)


class ZombieAttackQueueTests(unittest.TestCase):
    observe = zombie_fixture.ZombieQueueTests.observe

    @staticmethod
    def contact(world):
        world.walls = []
        world.zombie.x, world.zombie.y = 508, 180

    def test_real_contact_windup_single_hit_twelve_poses_recovery_and_next_attack(self):
        states = self.observe([], {50: [("quit",)]}, 51, self.contact)
        self.assertTrue(all(state["hp"] == 3 for state in states[:17]))
        self.assertEqual(states[17]["hp"], 2)
        self.assertTrue(all(state["hp"] == 2 for state in states[17:]))
        self.assertEqual({state["row"] for state in states[:48] if state["source"] == "zombie_attack"}, set(range(12)))
        self.assertTrue(all(state["position"] == (508, 180) and state["phase"] == 0 for state in states))
        self.assertTrue(all(state["attack_facing"] == "left" for state in states if state["attack_elapsed"] is not None))
        self.assertIsNone(states[47]["attack_elapsed"])
        self.assertIsNotNone(states[48]["attack_elapsed"])

    def test_real_focus_pause_walking_evasion_and_r_clear_attack_without_reload(self):
        states = self.observe([], {1: [("lost",), ("gained",)],
                                  2: [("down", zombie_fixture.main.p.SDLK_a)],
                                  20: [("down", zombie_fixture.main.p.SDLK_r)], 21: [("quit",)]},
                              22, self.contact)
        self.assertEqual(states[0]["attack_elapsed"], states[1]["attack_elapsed"])
        self.assertTrue(all(state["hp"] == 3 for state in states))
        self.assertTrue(any(state["attack_done"] for state in states))
        self.assertIsNone(states[-1]["attack_elapsed"])
        self.assertAlmostEqual(states[-1]["phase"], 1.5 / 64)

    def test_real_player_click_interrupts_zombie_windup_and_selects_hit_texture(self):
        states = self.observe([("click", 668, 521)], {20: [("quit",)]}, 21, self.contact)
        self.assertTrue(any(state["source"] == "zombie_attack" for state in states[:10]))
        hit = [state for state in states if state["stun"] > 0]
        self.assertTrue(hit)
        self.assertTrue(all(state["source"] == "zombie" and state["attack_elapsed"] is None for state in hit))
        self.assertTrue(all(state["hp"] == 3 for state in states))
        self.assertEqual(states[-1]["zombie_hp"], 4)


if __name__ == "__main__":
    unittest.main()
