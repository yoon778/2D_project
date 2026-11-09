import math
import unittest

from game.combat import CombatWorld
from game.core import Wall


class SprintTests(unittest.TestCase):
    def setUp(self):
        self.world = CombatWorld()
        self.world.walls = []
        self.world.player.x = 100.0
        self.world.player.aim_angle = 0.0
        self.world.zombie.stun_remaining = 10.0

    def test_diagonal_sprint_and_recovery_when_shift_is_released(self):
        world = self.world
        origin = (world.player.x, world.player.y)
        world.update(0.8, 1, 1, sprint=True)
        self.assertAlmostEqual(math.dist(origin, (world.player.x, world.player.y)), 108.0)
        self.assertAlmostEqual(world.stamina, 80.0)
        world.update(0.5, 1, 0)
        self.assertAlmostEqual(world.stamina, 90.0)

    def test_exhaustion_requires_25_stamina_before_held_shift_resumes(self):
        world = self.world
        world.update(4.0, 1, 0, sprint=True)
        self.assertAlmostEqual(world.player.x, 640.0)
        self.assertEqual(world.stamina, 0.0)
        world.update(1.25, 1, 0, sprint=True)
        self.assertAlmostEqual(world.player.x, 752.5)
        self.assertAlmostEqual(world.stamina, 25.0)
        world.update(0.2, 1, 0, sprint=True)
        self.assertAlmostEqual(world.player.x, 779.5)
        self.assertAlmostEqual(world.stamina, 20.0)

    def test_wall_and_attack_do_not_drain_stamina(self):
        world = self.world
        world.update(0.4, 1, 0, sprint=True)
        self.assertAlmostEqual(world.stamina, 90.0)
        world.walls = [Wall(world.player.x + 14, 150, 40, 100)]
        origin = world.player.x
        world.update(0.1, 1, 0, sprint=True)
        self.assertAlmostEqual(world.player.x, origin)
        self.assertAlmostEqual(world.stamina, 92.0)

        world.walls = []
        self.assertTrue(world.start_attack())
        world.update(0.2, 1, 0, sprint=True)
        self.assertAlmostEqual(world.player.x, origin)
        self.assertAlmostEqual(world.stamina, 96.0)

    def test_backstep_keeps_its_speed_and_reset_refills_stamina(self):
        world = self.world
        world.update(0.4, 1, 0, sprint=True)
        world.update(0.2, -1, 0, sprint=True)
        self.assertAlmostEqual(world.player.x, 141.0)
        self.assertAlmostEqual(world.stamina, 94.0)
        world.reset()
        self.assertEqual(world.stamina, 100.0)
