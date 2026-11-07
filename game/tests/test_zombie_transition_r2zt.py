"""R2-ZT attack facing and distance-driven return to walking."""
import math
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

TEST_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(TEST_DIR.parent))

from combat import CombatWorld, ZombieAttack
from combat_visual import CombatVisual
import test_zombie_visual_r2z as zombie_fixture


class ZombieTransitionTests(unittest.TestCase):
    def setUp(self):
        self.world = CombatWorld()
        self.world.walls = []
        self.world.zombie.x, self.world.zombie.y = 400, 180
        self.world.zombie.aim_angle = 0
        self.visual = CombatVisual.__new__(CombatVisual)
        source = zombie_fixture.zombie_metadata()
        source["canvas_size"] = [640, 2400]
        for col, (facing, _) in enumerate(zombie_fixture.FACINGS):
            source["facings"][facing]["resume"] = [
                [{"clip_topleft": [col * 80, row * 80, 80, 80],
                  "foot_pivot_topleft": [col * 80 + 40, row * 80 + 72],
                  "opaque_rows": {str(40 + row - 14): [[36, 38]]}}
                 for row in (14 + walk * 2, 15 + walk * 2)] for walk in range(8)]
        self.visual.metadata = {"zombie": source, "zombie_attack": zombie_fixture.zombie_attack_metadata()}
        self.visual.images = {"zombie": SimpleNamespace(h=2400, clip_draw=Mock())}
        self.visual.reset_zombie_animation()

    def advance(self, dt, *, paused=False):
        zombie = self.world.zombie
        before = zombie.x, zombie.y
        self.world.update(dt)
        self.visual.update_zombie(zombie, zombie.x - before[0], zombie.y - before[1], paused=paused)

    def pose(self):
        return self.visual._zombie_pose(self.world.zombie)

    def end_attack(self, phase_distance=62):
        zombie = self.world.zombie
        self.visual.update_zombie(zombie, phase_distance, 0)
        zombie.attack = ZombieAttack(0, "right", .79, True)
        self.visual.update_zombie(zombie, 0, 0)
        self.advance(.01)
        self.assertIsNone(zombie.attack)
        return self.visual.metadata["zombie"]["facings"]["right"]

    def test_25_degree_contact_keeps_visible_right_without_changing_physical_attack(self):
        self.advance(1 / 60)
        self.assertEqual(self.visual.zombie_locomotion.facing, "right")
        zombie = self.world.zombie
        angle = math.radians(25)
        self.world.player.x = zombie.x + 29 * math.cos(angle)
        self.world.player.y = zombie.y + 29 * math.sin(angle)
        self.advance(1 / 60)
        attack = zombie.attack
        self.assertIsNotNone(attack)
        self.assertEqual(attack.facing, "back_right")
        self.assertAlmostEqual(attack.angle, angle)
        source = self.visual.metadata["zombie_attack"]["facings"]
        self.assertEqual(self.pose(), ("zombie_attack", source["right"][0]))
        zombie.aim_angle = math.pi / 2
        self.advance(.2)
        self.assertIs(zombie.attack, attack)
        self.assertEqual(self.pose(), ("zombie_attack", source["right"][4]))

    def test_uninitialized_attack_uses_snapshot_and_new_attack_can_turn(self):
        zombie = self.world.zombie
        zombie.attack = ZombieAttack(math.radians(25), "back_right")
        self.visual.update_zombie(zombie, 0, 0)
        self.assertEqual(self.visual.zombie_locomotion.facing, "back_right")
        zombie.attack = ZombieAttack(math.pi / 2, "back")
        self.visual.update_zombie(zombie, 0, 0)
        self.assertEqual(self.visual.zombie_locomotion.facing, "back")

    def test_normal_end_resumes_for_eight_pixels_with_wrapped_target_and_current_mask(self):
        poses = self.end_attack()
        self.assertEqual(self.pose(), ("zombie", poses["idle"]))
        self.advance(2 / 90)
        self.assertEqual(self.pose(), ("zombie", poses["resume"][0][0]))
        self.visual.draw_zombie(self.world.zombie, 100, 200)
        self.visual.images["zombie"].clip_draw.assert_called_once_with(
            160, 1200, 80, 80, 100.0, 264.0, 160.0, 160.0)
        self.assertTrue(self.visual.zombie_contains(self.world.zombie, 100, 200, 93, 263))
        self.assertFalse(self.visual.zombie_contains(self.world.zombie, 100, 200, 93, 261))
        self.advance(0, paused=True)
        self.assertEqual(self.pose(), ("zombie", poses["resume"][0][0]))
        self.assertEqual(self.visual.zombie_locomotion.phase, 0)
        self.advance(2 / 90)
        self.assertEqual(self.pose(), ("zombie", poses["resume"][0][1]))
        self.advance(4 / 90)
        self.assertEqual(self.pose(), ("zombie", poses["walk"][0]))
        self.assertAlmostEqual(self.visual.zombie_locomotion.phase, 6 / 64)

    def test_actual_stop_ends_resume_at_idle_and_preserves_walk_phase(self):
        poses = self.end_attack()
        self.advance(2 / 90)
        self.assertEqual(self.pose(), ("zombie", poses["resume"][0][0]))
        phase = self.visual.zombie_locomotion.phase
        self.advance(0)
        self.assertEqual(self.pose(), ("zombie", poses["idle"]))
        self.assertEqual(self.visual.zombie_locomotion.phase, phase)
        self.advance(2 / 90)
        self.assertEqual(self.pose(), ("zombie", poses["walk"][0]))
        self.assertAlmostEqual(self.visual.zombie_locomotion.phase, 2 / 64)

    def test_recovery_and_movement_in_one_update_use_the_pre_move_phase(self):
        zombie = self.world.zombie
        self.visual.update_zombie(zombie, 7, 0)
        zombie.attack = ZombieAttack(0, "right", .79, True)
        self.visual.update_zombie(zombie, 0, 0)
        self.advance(.01 + 2 / 90)
        self.assertIsNone(zombie.attack)
        poses = self.visual.metadata["zombie"]["facings"]["right"]
        self.assertEqual(self.pose(), ("zombie", poses["resume"][1][0]))
        self.assertAlmostEqual(self.visual.zombie_locomotion.phase, 9 / 64)

    def test_cancelled_attack_or_legacy_metadata_returns_to_regular_walk(self):
        zombie = self.world.zombie
        zombie.attack = ZombieAttack(0, "right", .4)
        self.visual.update_zombie(zombie, 0, 0)
        zombie.attack = None
        self.advance(1 / 90)
        poses = self.visual.metadata["zombie"]["facings"]["right"]
        self.assertEqual(self.pose(), ("zombie", poses["walk"][0]))
        poses.pop("resume")
        self.end_attack(phase_distance=0)
        self.advance(1 / 90)
        self.assertEqual(self.pose(), ("zombie", poses["walk"][0]))
        self.advance(0, paused=True)
        self.assertEqual(self.pose(), ("zombie", poses["idle"]))

    def test_stun_death_new_attack_and_reset_clear_pending_resume(self):
        for reason in ("stun", "death", "new_attack", "reset"):
            with self.subTest(reason=reason):
                self.setUp()
                self.end_attack()
                zombie = self.world.zombie
                if reason == "stun":
                    zombie.stun_remaining = .4
                elif reason == "death":
                    zombie.hp = 0
                elif reason == "new_attack":
                    zombie.attack = ZombieAttack(0, "right", .05)
                else:
                    self.visual.reset_zombie_animation()
                self.visual.update_zombie(zombie, 0, 0)
                zombie.stun_remaining, zombie.hp, zombie.attack = 0, 5, None
                self.advance(1 / 90)
                poses = self.visual.metadata["zombie"]["facings"]["right"]
                walk = self.visual.zombie_locomotion.walk_frame_index(8)
                self.assertEqual(self.pose(), ("zombie", poses["walk"][walk - 1]))


class ZombieTransitionQueueTests(unittest.TestCase):
    observe = zombie_fixture.ZombieQueueTests.observe

    def test_real_recovery_resumes_through_both_rows_and_pauses_on_focus_loss(self):
        def setup(world):
            world.walls = []
            world.zombie.x, world.zombie.y = 508, 180

        states = self.observe([], {34: [("down", zombie_fixture.main.p.SDLK_a)],
                                   50: [("lost",), ("gained",)], 56: [("quit",)]}, 57, setup)
        self.assertEqual([state["row"] for state in states[47:55]], [0, 16, 16, 16, 17, 17, 17, 2])
        self.assertAlmostEqual(states[49]["phase"], 3 / 64)
        self.assertEqual(states[50]["phase"], states[49]["phase"])
        self.assertAlmostEqual(states[54]["phase"], 9 / 64)


if __name__ == "__main__":
    unittest.main()
