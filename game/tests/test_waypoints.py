import math
import unittest

from game.core import Wall
from game.delivery import MAX_WAYPOINTS, DeliveryWorld


class WaypointTests(unittest.TestCase):
    def test_add_checks_map_bounds_and_capacity_and_remove_takes_last(self):
        world = DeliveryWorld()
        width, height = world.world_size
        for position in ((-1, 0), (0, -1), (width + 1, 0), (0, height + 1), (math.nan, 0), (0, math.inf)):
            with self.subTest(position=position):
                self.assertFalse(world.add_waypoint(position))
        route = [(0, 0), (width, height), *[(index, index) for index in range(1, MAX_WAYPOINTS - 1)]]
        for position in route:
            self.assertTrue(world.add_waypoint(position))
        self.assertFalse(world.add_waypoint((42, 42)))
        self.assertEqual(world.waypoints, route)
        self.assertTrue(world.remove_last_waypoint())
        self.assertEqual(world.waypoints, route[:-1])
        for _ in route[:-1]:
            self.assertTrue(world.remove_last_waypoint())
        self.assertFalse(world.remove_last_waypoint())

    def test_advance_only_consumes_first_visible_point_within_32_pixels(self):
        world = DeliveryWorld()
        world.player.x, world.player.y = (150, 100)
        first, second = (183, 100), (170, 100)
        self.assertTrue(world.add_waypoint(first))
        self.assertTrue(world.add_waypoint(second))
        self.assertFalse(world.advance_waypoint())

        world.player.x = 151
        world.walls.append(Wall(174, 94, 2, 12))
        self.assertFalse(world.advance_waypoint())
        self.assertEqual(world.waypoints, [first, second])
        world.walls.pop()
        self.assertTrue(world.advance_waypoint())
        self.assertEqual(world.waypoints, [second])
        self.assertTrue(world.advance_waypoint())
        self.assertFalse(world.advance_waypoint())

    def test_reset_and_contract_selection_clear_route_without_changing_delivery(self):
        world = DeliveryWorld(two_stop_unlocked=True)
        for index in (0, 2):
            with self.subTest(contract=index):
                self.assertTrue(world.add_waypoint((170, 150)))
                self.assertTrue(world.select_contract(index))
                self.assertEqual(world.waypoints, [])
                self.assertTrue(world.interact())
                for stop in world.contract.stops:
                    self.assertTrue(world.add_waypoint(stop.position))
                    world.player.x, world.player.y = stop.position
                    self.assertTrue(world.interact())
                self.assertEqual(world.result, "delivered")
                self.assertFalse(world.advance_waypoint())
                world.reset()
                self.assertEqual(world.waypoints, [])
                self.assertEqual(world.parcel, "waiting")

    def test_skip_and_arrival_keep_remaining_waypoint_numbers_until_route_is_empty(self):
        world = DeliveryWorld()
        world.player.x, world.player.y = (150, 100)
        first, second, third, fourth = (230, 100), (170, 100), (300, 100), (400, 100)
        self.assertFalse(world.skip_waypoint())
        for point in (first, second, third):
            self.assertTrue(world.add_waypoint(point))
        self.assertEqual(world.first_waypoint_number, 1)

        self.assertTrue(world.skip_waypoint())
        self.assertEqual(world.waypoints, [second, third])
        self.assertEqual(world.first_waypoint_number, 2)
        self.assertTrue(world.advance_waypoint())
        self.assertEqual(world.waypoints, [third])
        self.assertEqual(world.first_waypoint_number, 3)

        self.assertTrue(world.add_waypoint(fourth))
        self.assertTrue(world.remove_last_waypoint())
        self.assertEqual(world.waypoints, [third])
        self.assertEqual(world.first_waypoint_number, 3)
        self.assertTrue(world.remove_last_waypoint())
        self.assertEqual(world.first_waypoint_number, 1)
        self.assertFalse(world.skip_waypoint())
        self.assertTrue(world.add_waypoint(first))
        self.assertTrue(world.add_waypoint(second))
        self.assertTrue(world.skip_waypoint())
        self.assertEqual(world.first_waypoint_number, 2)
        world.reset()
        self.assertEqual(world.waypoints, [])
        self.assertEqual(world.first_waypoint_number, 1)


if __name__ == "__main__":
    unittest.main()
