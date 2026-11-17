import unittest

from game.combat import HEAVY_ZOMBIE_APPEARANCE, Zombie
from game.delivery import DeliveryWorld
from game.zombie_navigation import can_walk_direct, find_route


class ParkingShutterTests(unittest.TestCase):
    def setUp(self):
        self.world = DeliveryWorld(two_stop_unlocked=True)
        self.assertTrue(self.world.select_contract(3))

    def hold(self, dt, *, pressed=False, damaged=False):
        return self.world.update_interaction(dt, held=True, pressed=pressed, moving=False, damaged=damaged)

    def collect_parcels(self):
        world = self.world
        self.assertTrue(world.skip_route_sequence())
        self.assertTrue(self.hold(0.5, pressed=True))
        self.assertEqual(world.mission_phase, "delivering")

    def test_shutter_exists_for_each_shop_contract_and_resets_open(self):
        world = self.world
        self.assertIn((2290, 1350), world.streetlights)
        for zombie in world.zombies:
            point = (zombie.x, zombie.y)
            self.assertTrue(can_walk_direct(point, point, world.walls), point)
        world.player.x, world.player.y = world.shutter_position
        self.assertFalse(self.hold(0.7, pressed=True))
        world.player.x, world.player.y = world.contract.player_start
        self.collect_parcels()
        world.player.x, world.player.y = world.shutter_position
        self.assertTrue(self.hold(0.7, pressed=True))
        self.assertTrue(world.shutter_closed)
        self.assertIn(world.shutter_wall, world.walls)
        world.reset()
        self.assertFalse(world.shutter_closed)
        self.assertNotIn(world.shutter_wall, world.walls)
        self.assertEqual(world.streetlights.count((2290, 1350)), 1)
        for index in (0, 2):
            with self.subTest(contract=index):
                self.assertTrue(world.select_contract(index))
                self.assertIsNotNone(world.shutter_position)
                self.assertIn((2290, 1350), world.streetlights)
                self.assertTrue(self.hold(0.5, pressed=True))
                world.player.x, world.player.y = world.shutter_position
                self.assertTrue(self.hold(0.7, pressed=True))
        self.assertTrue(world.select_contract(1))
        self.assertIsNone(world.shutter_position)
        self.assertFalse(world.can_close_shutter())
        self.assertNotIn((2290, 1350), world.streetlights)

    def test_closing_cancels_if_damaged_or_zombie_enters_the_doorway(self):
        world = self.world
        self.collect_parcels()
        world.player.x, world.player.y = world.shutter_position
        self.assertFalse(self.hold(0.4, pressed=True))
        self.assertEqual(world.interaction_action, "shutter")
        self.assertFalse(self.hold(0.3, damaged=True))
        self.assertIsNone(world.interaction_action)
        wall = world.shutter_wall
        world.player.x, world.player.y = wall.x - 5, wall.y + 15
        self.assertFalse(world.can_close_shutter())
        world.player.x, world.player.y = world.shutter_position
        self.assertFalse(self.hold(0.4, pressed=True))
        zombie = Zombie(wall.x - 5, wall.y + wall.depth / 2)
        world.zombies.append(zombie)
        self.assertFalse(self.hold(0.3))
        self.assertIsNone(world.interaction_action)
        self.assertFalse(world.shutter_closed)
        zombie.x -= 40
        self.assertFalse(self.hold(0.7))
        self.assertTrue(self.hold(0.7, pressed=True))

    def test_bottle_lures_group_into_parking_lot_and_closed_shutter_contains_it(self):
        world = self.world
        self.collect_parcels()
        # Isolate the parking group from the other shop enemies.
        world.zombies = [zombie for zombie in world.zombies[len(world.contract.zombie_starts):]
                         if zombie.appearance != HEAVY_ZOMBIE_APPEARANCE and not zombie.patrol_points]
        self.assertEqual(len(world.zombies), 8)
        outside = (2105, 1258)
        world.player.x, world.player.y = outside
        self.assertTrue(world.pick_up_bottle())
        self.assertEqual(world.bottle_throw_hint(world.shutter_lure), "주차장 안쪽으로 유인")
        self.assertEqual(world.bottle_throw_hint((2070, 1240)), "병 던지기")
        self.assertTrue(world.throw_bottle(world.shutter_lure))
        self.assertTrue(can_walk_direct((2110, 1340), world.shutter_lure, world.walls))
        for _ in range(34):
            world.update(0.05)
        self.assertTrue(all(zombie.x > 2186 for zombie in world.zombies))
        self.assertTrue(self.hold(0.7, pressed=True))
        self.assertFalse(can_walk_direct((2110, 1340), world.shutter_lure, world.walls))
        self.assertEqual(find_route(world.shutter_lure, outside, world.walls, world.world_size), [])
        self.assertEqual(world.player_hp, 3)


if __name__ == "__main__":
    unittest.main()
