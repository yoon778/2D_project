import unittest

from game.core import Wall, wall_blocks
from game.delivery import DeliveryWorld
from game.zombie_navigation import can_walk_direct


class BridgePuzzleTests(unittest.TestCase):
    def setUp(self):
        self.world = DeliveryWorld(two_stop_unlocked=True)
        self.assertTrue(self.world.select_contract(3))
        self.puzzle = self.world.bridge_puzzle

    def hold(self, duration, *, pressed=True, held=True):
        return self.world.update_interaction(duration, held=held, pressed=pressed, moving=False, damaged=False)

    def move_to(self, position):
        self.world.player.x, self.world.player.y = position

    def deliver(self):
        self.move_to(self.world.pickup)
        self.assertTrue(self.hold(0.50))
        self.move_to(self.world.destination)
        self.assertTrue(self.hold(1.00))

    def test_note_requires_return_route_clear_sight_and_yields_to_circuit(self):
        world, puzzle = self.world, self.puzzle
        self.move_to(puzzle.note_position)
        self.assertFalse(world.can_read_bridge_note())
        self.deliver()
        x, y = puzzle.note_position
        self.move_to((x + 43, y))
        self.assertFalse(world.can_read_bridge_note())
        self.move_to((x + 22, y))
        self.assertTrue(world.can_read_bridge_note())
        world.walls.append(Wall(x + 8, y - 10, 4, 20))
        self.assertFalse(world.can_read_bridge_note())
        world.walls.pop()

        self.move_to(puzzle.key_position)
        self.assertTrue(self.hold(0.5))
        self.move_to((2568, 1282))
        self.assertTrue(world.can_open_bridge_panel())
        self.assertFalse(world.can_read_bridge_note())

    def test_panel_requires_key_and_keeps_tile_rotations_when_closed(self):
        world, puzzle = self.world, self.puzzle
        self.move_to(puzzle.key_position)
        self.assertFalse(self.hold(0.5))
        self.deliver()
        self.move_to(puzzle.panel_position)
        self.assertTrue(world.can_reach_bridge_panel())
        self.assertFalse(self.hold(0.7))
        self.move_to(puzzle.key_position)
        self.assertFalse(self.hold(0.49))
        self.assertFalse(self.hold(0.01, held=False, pressed=False))
        self.assertFalse(puzzle.has_key)
        self.assertTrue(self.hold(0.5))
        self.move_to(puzzle.panel_position)
        self.assertTrue(self.hold(0.7))
        self.assertFalse(world.rotate_bridge_tile(0))
        world.close_bridge_panel()
        self.assertFalse(world.rotate_bridge_tile(0))
        self.assertTrue(self.hold(0.7))
        self.assertEqual(tuple(puzzle.rotations), (3, 1, 3))

    def test_shortcut_opens_only_on_connection_and_motor_draws_nearby_zombie(self):
        world, puzzle = self.world, self.puzzle
        crossing = (puzzle.panel_position, (2545, 1403))
        bypass = ((2750, 987), (2750, 1400), (2960, 1400), (2960, 1740), (2435, 1740), (2435, 2235))
        self.assertFalse(can_walk_direct(*crossing, world.walls))
        self.assertTrue(all(can_walk_direct(a, b, world.walls) for a, b in zip(bypass, bypass[1:])))

        self.deliver()
        self.move_to(puzzle.key_position)
        self.assertTrue(self.hold(0.5))
        self.move_to(puzzle.panel_position)
        self.assertTrue(self.hold(0.7))
        for index in (0, 0, 1, 1, 1):
            self.assertFalse(world.rotate_bridge_tile(index))
        self.assertFalse(puzzle.bridge_down)
        self.assertFalse(can_walk_direct(*crossing, world.walls))
        self.assertTrue(world.rotate_bridge_tile(2))
        self.assertTrue(puzzle.bridge_down)
        self.assertTrue(can_walk_direct(*crossing, world.walls))
        self.assertFalse(puzzle.panel_open)

        nearby = next(z for z in world.zombies if (z.x, z.y) == (2370, 1465))
        self.assertTrue(any(wall_blocks((nearby.x, nearby.y), puzzle.bridge_position, wall) for wall in world.walls))
        self.assertEqual(nearby.heard_at, puzzle.bridge_position)
        self.assertTrue(all(z.heard_at is None for z in world.zombies if z is not nearby))
        world.update(0.05)
        self.assertEqual((nearby.state, nearby.target), ("investigate", puzzle.bridge_position))
        self.assertFalse(world.rotate_bridge_tile(2))
        self.assertIsNone(nearby.heard_at)

    def test_restart_restores_the_raised_bridge_and_other_contracts_exclude_it(self):
        self.deliver()
        self.move_to(self.puzzle.key_position)
        self.assertTrue(self.hold(0.5))
        self.world.reset()
        self.assertFalse(self.world.bridge_puzzle.has_key)
        self.assertIn(self.world.bridge_puzzle.bridge_wall, self.world.walls)
        for index in (0, 1, 2):
            self.assertTrue(self.world.select_contract(index))
            self.assertIsNone(self.world.bridge_puzzle)
            self.assertFalse(self.world.can_reach_bridge_panel())
            self.assertTrue(can_walk_direct((2545, 1302), (2545, 1403), self.world.walls))


if __name__ == "__main__":
    unittest.main()
