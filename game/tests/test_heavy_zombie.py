import math
import unittest

from game.combat import HEAVY_ZOMBIE_APPEARANCE, CombatWorld, Zombie
from game.core import PLAYER_RADIUS
from game.delivery import DeliveryWorld, VEHICLE_ALARM_RANGE


def hold_interaction(world, duration):
    return world.update_interaction(duration, held=True, pressed=True, moving=False, damaged=False)


class HeavyZombieTests(unittest.TestCase):
    def test_only_shop_round_trip_spawns_one_heavy_zombie(self):
        world = DeliveryWorld(two_stop_unlocked=True)
        for contract in (0, 1, 2):
            with self.subTest(contract=contract):
                self.assertTrue(world.select_contract(contract))
                self.assertFalse(any(zombie.appearance == HEAVY_ZOMBIE_APPEARANCE for zombie in world.zombies))

        self.assertTrue(world.select_contract(3))
        for _ in range(2):
            heavy, = [zombie for zombie in world.zombies if zombie.appearance == HEAVY_ZOMBIE_APPEARANCE]
            self.assertEqual(heavy.hp, 18)
            self.assertGreater(heavy.hp, 3 * Zombie(0, 0).hp)
            self.assertLess(heavy.hp, 4 * Zombie(0, 0).hp)
            self.assertGreater(math.dist((heavy.x, heavy.y), (1794, 979)), VEHICLE_ALARM_RANGE)
            heavy.hp = 0
            world.reset()

    def test_heavy_moves_slower_in_chase_and_investigation(self):
        for state, player, target in (("chase", (480, 180), None), ("investigate", (800, 600), (480, 180))):
            with self.subTest(state=state):
                world = CombatWorld()
                world.walls.clear()
                world.player.x, world.player.y = player
                heavy = Zombie(580, 180, state=state, target=target, appearance=HEAVY_ZOMBIE_APPEARANCE)
                normal = Zombie(580, 180, state=state, target=target)
                world.zombies = [heavy, normal]
                world.update(0.5)
                self.assertAlmostEqual(heavy.x, 553.0)
                self.assertAlmostEqual(normal.x, 535.0)

    def test_heavy_hit_and_recovery_use_its_own_boundaries(self):
        world = CombatWorld()
        world.player.x, world.player.y = 600, 100
        heavy = Zombie(620, 100, appearance=HEAVY_ZOMBIE_APPEARANCE, hp=18)
        world.zombies = [heavy]

        world.update(0.599)
        attack = heavy.attack
        self.assertEqual(world.player_hp, 3)
        self.assertAlmostEqual(attack.hit_time, 0.6)
        self.assertAlmostEqual(attack.duration, 1.15)
        world.update(0.001)
        self.assertEqual(world.player_hp, 2)
        self.assertIs(heavy.attack, attack)
        world.update(0.549)
        self.assertEqual(world.player_hp, 2)
        self.assertIs(heavy.attack, attack)
        world.update(0.001)
        self.assertIsNone(heavy.attack)

    def test_heavy_follows_bottle_then_shutter_blocks_its_return(self):
        world = DeliveryWorld()
        self.assertTrue(world.select_contract(3))
        self.assertTrue(world.skip_route_sequence())
        self.assertTrue(hold_interaction(world, 0.5))
        # Isolate the parking group from the other shop enemies.
        world.zombies = [zombie for zombie in world.zombies[len(world.contract.zombie_starts):]
                         if not zombie.patrol_points]
        heavy = world.zombies[-1]
        wall = world.shutter_wall
        inside = wall.x + wall.width + PLAYER_RADIUS
        world.player.x, world.player.y = 2105, 1258
        self.assertTrue(world.pick_up_bottle())
        self.assertTrue(world.throw_bottle(world.shutter_lure))

        world.update(1.7)
        self.assertTrue(all(zombie.x > inside for zombie in world.zombies[:-1]))
        self.assertLess(heavy.x, inside)
        world.update(1.2)
        self.assertGreater(heavy.x, inside)
        self.assertTrue(hold_interaction(world, 0.7))

        # A sprint outside the lot gives the heavy zombie a fresh reason to try the door.
        world.player.x, world.player.y, world.player.aim_angle = 2110, 1385, math.pi / 2
        world.update(0.2, axis_y=1, sprint=True)
        self.assertTrue(world.sprinting)
        self.assertIsNotNone(world.sprint_step)
        self.assertEqual(heavy.target, world.sprint_step)
        self.assertLess(heavy.target[0], wall.x)
        world.update(2.0)
        self.assertGreater(heavy.x, inside)
        self.assertEqual(heavy.hp, 18)
        self.assertEqual(world.player_hp, 3)


if __name__ == "__main__":
    unittest.main()
