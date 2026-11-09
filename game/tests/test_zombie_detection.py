"""Regression scenarios for perception, remembered positions and wall routes."""
import math
import unittest

from game.combat import CombatWorld
from game.core import PLAYER_RADIUS, Wall


class ZombieDetectionTests(unittest.TestCase):
    def setUp(self):
        self.world = CombatWorld()
        self.world.player.x, self.world.player.y = 500, 440
        self.world.zombie.x, self.world.zombie.y = 500, 280

    def test_hidden_and_silent_player_does_not_alert_zombie(self):
        world = self.world
        world.update(1.0)
        self.assertEqual(world.zombie.state, "idle")
        self.assertIsNone(world.zombie.target)
        self.assertEqual((world.zombie.x, world.zombie.y), (500, 280))

    def test_missed_attack_is_heard_around_wall_and_remembers_original_position(self):
        world = self.world
        self.assertTrue(world.start_attack())
        world.update(0.001)
        self.assertEqual(world.zombie.state, "investigate")
        self.assertEqual(world.zombie.target, (500, 440))
        # A silent relocation isolates the remembered position from later footsteps.
        world.player.x, world.player.y = 180, 690

        leftmost = world.zombie.x
        for _ in range(250):
            world.update(0.02)
            x, y = world.zombie.x, world.zombie.y
            wall = world.walls[0]
            gap_x = max(wall.x - x, 0, x - wall.x - wall.width)
            gap_y = max(wall.y - y, 0, y - wall.y - wall.depth)
            self.assertGreaterEqual(math.hypot(gap_x, gap_y), PLAYER_RADIUS - 1e-7)
            leftmost = min(leftmost, x)
            if world.zombie.state == "search":
                break
        self.assertEqual(world.zombie.state, "search")
        self.assertLessEqual(leftmost, 400 - PLAYER_RADIUS)
        self.assertAlmostEqual(world.zombie.x, 500)
        self.assertAlmostEqual(world.zombie.y, 440)
        self.assertEqual(world.zombie.hp, 5)

    def test_last_seen_position_starts_three_second_search_then_idle(self):
        world = self.world
        world.player.y = 310
        world.zombie.y = 250
        world.update(0.1)
        self.assertEqual((world.zombie.state, world.zombie.target), ("chase", (500, 310)))

        world.player.y = 440
        world.update(51 / 90)
        self.assertEqual((world.zombie.state, world.zombie.target), ("search", (500, 310)))
        self.assertAlmostEqual(world.zombie.y, 310)
        self.assertAlmostEqual(world.zombie.search_remaining, 3.0)
        angle = world.zombie.aim_angle
        world.update(2.999)
        self.assertEqual(world.zombie.state, "search")
        self.assertNotEqual(world.zombie.aim_angle, angle)
        world.update(0.001)
        self.assertEqual(world.zombie.state, "idle")
        self.assertIsNone(world.zombie.target)

    def test_reacquiring_sight_interrupts_search_and_reset_discards_memory(self):
        world = self.world
        world.player.y = 310
        world.update(0.01)
        world.player.y = 440
        world.update(1.0)
        self.assertEqual(world.zombie.state, "search")
        world.player.x, world.player.y = 580, 310
        world.update(0.01)
        self.assertEqual((world.zombie.state, world.zombie.target), ("chase", (580, 310)))
        self.assertEqual(world.zombie.search_remaining, 0.0)
        world.reset()
        self.assertEqual((world.zombie.state, world.zombie.target), ("idle", None))

    def test_actual_walk_and_sprint_steps_use_different_hearing_ranges(self):
        for y, sprint, expected in ((316, False, "investigate"), (260, False, "idle"),
                                   (260, True, "investigate")):
            with self.subTest(y=y, sprint=sprint):
                world = CombatWorld()
                world.walls = [Wall(400, 330, 220, 8)]
                world.player.x, world.player.y, world.player.aim_angle = 464, y, 0.0
                world.zombie.x, world.zombie.y = 500, 352
                world.update(35 / (135 if sprint else 90), 1, 0, sprint=sprint)
                self.assertEqual(world.zombie.state, "idle")
                world.update(0.02, 1, 0, sprint=sprint)
                self.assertEqual(world.zombie.state, expected)
                if expected == "investigate":
                    self.assertAlmostEqual(world.zombie.target[0], 500, delta=0.14)
                    self.assertEqual(world.zombie.target[1], y)

    def test_sprinting_against_wall_does_not_make_a_footstep(self):
        world = self.world
        world.player.y = 404
        world.update(1.0, 0, -1, sprint=True)
        self.assertEqual(world.player.y, 404)
        self.assertEqual(world.zombie.state, "idle")
