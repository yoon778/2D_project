import math
import unittest

from game.combat import SNEAK_SPEED, Zombie
from game.core import WALK_SPEED, Wall, wall_blocks
from game.delivery import BUS_BROADCAST_COOLDOWN, BUS_STOP, FRONT_HOME_STOP, DeliveryWorld
from game.zombie_navigation import can_walk_direct, find_route


class DistrictGimmickTests(unittest.TestCase):
    def setUp(self):
        self.world = DeliveryWorld(two_stop_unlocked=True)

    def move(self, point):
        self.world.player.x, self.world.player.y = point

    def hold(self, dt, *, pressed=True, held=True, moving=False, damaged=False):
        return self.world.update_interaction(dt, pressed=pressed, held=held, moving=moving, damaged=damaged)

    def assert_route(self, *points):
        self.assertTrue(all(can_walk_direct(a, b, self.world.walls) for a, b in zip(points, points[1:])))

    def walk(self, target, *, sneak=False):
        player = self.world.player
        dx, dy = target[0] - player.x, target[1] - player.y
        distance = math.hypot(dx, dy)
        player.aim_angle = math.atan2(dy, dx)
        remaining = distance / (SNEAK_SPEED if sneak else WALK_SPEED)
        while remaining > 0:
            dt = min(remaining, 1 / 60)
            self.world.update(dt, dx / distance, dy / distance, sneak=sneak)
            remaining -= dt
        self.assertAlmostEqual(player.x, target[0])
        self.assertAlmostEqual(player.y, target[1])

    def hold_in_world(self, frames):
        completed = False
        for frame in range(frames):
            hp = self.world.player_hp
            self.world.update(1 / 60)
            completed = self.hold(1 / 60, pressed=frame == 0, damaged=self.world.player_hp < hp)
        return completed

    def test_bus_broadcast_uses_speaker_noise_and_rearms_after_play_time(self):
        world = self.world
        self.assertTrue(world.select_contract(0))
        switch = world.bus_switch_position
        speaker = world.bus_speaker_position
        self.move(switch)
        self.assertFalse(self.hold(0.7))
        self.move(world.pickup)
        self.assertTrue(self.hold(0.5))
        self.move((switch[0], switch[1] - 20))
        blocker = Wall(switch[0] - 8, switch[1] - 12, 16, 4)
        world.walls.append(blocker)
        self.assertFalse(world.can_start_bus_broadcast())
        world.walls.remove(blocker)

        guard = next(zombie for zombie in world.zombies if (zombie.x, zombie.y) == (2338, 1865))
        far = Zombie(speaker[0] - 311, speaker[1])
        world.zombies = [guard, far]
        self.assertTrue(any(wall_blocks((guard.x, guard.y), speaker, wall) for wall in world.walls))
        self.assertFalse(self.hold(0.69))
        self.assertIsNone(world.bus_broadcast_source)
        self.assertFalse(self.hold(0.01, pressed=False, damaged=True))
        self.assertIsNone(guard.heard_at)
        self.assertFalse(self.hold(0.01, pressed=False))
        self.assertTrue(self.hold(0.7))
        self.assertEqual(world.bus_broadcast_source, speaker)
        self.assertEqual(guard.heard_at, speaker)
        self.assertIsNone(far.heard_at)
        self.assertEqual(world.bus_broadcast_cooldown, BUS_BROADCAST_COOLDOWN)
        self.assertFalse(self.hold(0.70))
        world.update(0.0)
        self.assertIsNone(world.bus_broadcast_source)
        self.assertEqual(world.bus_broadcast_cooldown, BUS_BROADCAST_COOLDOWN)
        start = math.dist((guard.x, guard.y), speaker)
        world.update(0.2)
        self.assertEqual((guard.state, guard.target), ("investigate", speaker))
        self.assertLess(math.dist((guard.x, guard.y), speaker), start)
        world.zombies.clear()
        while world.bus_broadcast_cooldown > 1:
            world.update(1)
        world.update(world.bus_broadcast_cooldown - 0.01)
        self.assertFalse(world.can_start_bus_broadcast())
        world.update(0.01)
        self.assertTrue(world.can_start_bus_broadcast())
        self.assertTrue(self.hold(0.70))
        world.reset()
        self.assertEqual(world.bus_broadcast_cooldown, 0.0)
        self.assertIsNone(world.bus_broadcast_source)

    def test_bus_has_two_passable_approaches_each_time_it_is_a_delivery_stop(self):
        world = self.world
        for index in (0, 2, 3):
            with self.subTest(contract=index):
                self.assertTrue(world.select_contract(index))
                for approach_x in (2170, 2394):
                    self.assert_route((approach_x, 1740), (approach_x, 1860), BUS_STOP.position)
                self.assertTrue(find_route(world.contract.stops[0].position, BUS_STOP.position,
                                           world.walls, world.world_size))
        self.assertTrue(world.select_contract(1))
        self.assertIsNone(world.bus_switch_position)
        self.assertFalse(world.can_start_bus_broadcast())

    def test_bus_guards_let_a_walker_reach_the_switch_then_turn_to_the_speaker(self):
        world = self.world
        self.assertTrue(world.select_contract(3))
        self.assertTrue(world.skip_route_sequence())
        self.assertTrue(self.hold(0.50))
        world.zombies = [zombie for zombie in world.zombies
                         if (zombie.x, zombie.y) in ((2338, 1865), (2390, 1850))]
        self.assertEqual(len(world.zombies), 2)
        self.move((2512, 1422))
        for waypoint in ((2512, 1688), (2290, 1688), (2290, 1720)):
            self.walk(waypoint)
            self.assertTrue(all(zombie.state == "idle" for zombie in world.zombies))
        self.assertTrue(self.hold(0.70))
        world.update(0.05)
        self.assertTrue(all(zombie.state == "investigate" and zombie.target == world.bus_speaker_position
                            for zombie in world.zombies))
        for waypoint in ((2394, 1740), (2394, 1860), BUS_STOP.position):
            self.walk(waypoint)
            self.assertTrue(all(zombie.state != "chase" for zombie in world.zombies))
        self.assertTrue(self.hold_in_world(60))
        self.assertEqual(world.player_hp, 3)

    def test_front_gate_hold_opens_shortcut_without_touching_rear_gate_or_bypass(self):
        world = self.world
        self.assertTrue(world.select_contract(1))
        front_gate, rear_gate = world.front_gate, world.gate
        approach, end = (3067, 1895), (3067, 1969)
        self.assertFalse(can_walk_direct(approach, end, world.walls))
        self.assert_route(approach, (3067, 1880), (3180, 1880), (3180, 1969), FRONT_HOME_STOP.position)
        self.move(approach)
        self.assertFalse(self.hold(0.70))
        self.move(world.pickup)
        self.assertTrue(self.hold(0.50))
        self.move(approach)
        self.assertTrue(world.can_open_front_gate())
        listener = Zombie(2984, 1967)
        world.zombies.append(listener)
        self.assertFalse(self.hold(0.69))
        self.assertFalse(self.hold(0.01, pressed=False, moving=True))
        self.assertIn(front_gate, world.walls)
        self.assertFalse(self.hold(0.70, pressed=False))
        self.assertTrue(self.hold(0.70))
        self.assertIsNone(world.front_gate)
        self.assertIs(world.gate, rear_gate)
        self.assertIn(rear_gate, world.walls)
        self.assert_route(approach, end, FRONT_HOME_STOP.position)
        self.assertEqual(listener.heard_at, world.front_gate_position)
        self.assertFalse(self.hold(0.70))
        world.reset()
        self.assertIn(world.front_gate, world.walls)
        for index in (0, 2, 3):
            self.assertTrue(world.select_contract(index))
            self.assertIsNone(world.front_gate_position)
            self.assertFalse(world.can_open_front_gate())

    def test_front_guard_chases_after_shortcut_but_leaves_time_for_delivery_and_exit(self):
        world = self.world
        self.assertTrue(world.select_contract(1))
        self.assertTrue(self.hold(0.50))
        world.zombies = [zombie for zombie in world.zombies if (zombie.x, zombie.y) == (2898, 1984)]
        guard, = world.zombies
        self.move((2700, 1880))
        self.walk((3067, 1880))
        self.walk((3067, 1895))
        self.assertEqual(guard.state, "idle")
        self.assertTrue(self.hold_in_world(42))
        self.walk((3067, 1947))
        self.walk(FRONT_HOME_STOP.position)
        self.assertTrue(self.hold_in_world(60))
        self.assertEqual(guard.state, "chase")
        self.assertGreater(math.dist((guard.x, guard.y), FRONT_HOME_STOP.position), 45)
        self.walk((3180, 1969))
        self.assertEqual(world.player_hp, 3)

    def test_shop_side_patrols_investigate_a_swing_from_behind_the_wall_at_different_times(self):
        world = self.world
        strike_position = (1987, 901)
        for patrol_elapsed in (0.0, .7):
            with self.subTest(patrol_elapsed=patrol_elapsed):
                self.assertTrue(world.select_contract(3))
                self.assertTrue(world.skip_route_sequence())
                self.assertTrue(self.hold(.50))
                patrols = [zombie for zombie in world.zombies if zombie.patrol_points]
                self.assertEqual(len(patrols), 2)
                for zombie in patrols:
                    self.assertEqual(zombie.state, "patrol")
                    self.assert_route(*zombie.patrol_points)
                world.update(patrol_elapsed)
                self.move(strike_position)
                world.player_invulnerable_remaining = 5.0
                self.assertTrue(all(not world._player_line_clear(zombie) for zombie in patrols))
                self.assertTrue(world.start_attack("back", stationary_swing=True))
                self.assertTrue(all(zombie.heard_at == strike_position for zombie in patrols))
                world.update(.05)
                self.assertTrue(all(zombie.state == "investigate" and zombie.target == strike_position
                                    for zombie in patrols))
                arrivals = {}
                for tick in range(2, 101):
                    world.update(.05)
                    for index, zombie in enumerate(patrols):
                        if math.dist((zombie.x, zombie.y), strike_position) <= 100:
                            arrivals.setdefault(index, tick * .05)
                    if len(arrivals) == 2:
                        break
                self.assertGreaterEqual(arrivals[0], 2.5)
                self.assertLess(arrivals[0], 3.1)
                self.assertGreater(arrivals[1] - arrivals[0], .75)
                self.assertLess(arrivals[1], 4.5)
        patrol_routes = {zombie.patrol_points for zombie in patrols}
        for index in (0, 1, 2):
            self.assertTrue(world.select_contract(index))
            self.assertFalse(any(zombie.patrol_points in patrol_routes for zombie in world.zombies))

    def test_bottle_and_ctrl_keep_the_shop_patrols_from_entering_the_delivery_route(self):
        world = self.world
        self.assertTrue(world.select_contract(3))
        self.assertTrue(world.skip_route_sequence())
        self.assertTrue(self.hold(.50))
        patrols = [zombie for zombie in world.zombies if zombie.patrol_points]
        self.assertEqual(len(patrols), 2)
        self.walk((2280, 907), sneak=True)
        self.assertTrue(world.pick_up_bottle())
        for point in ((2200, 907), (2200, 875), (2053, 875)):
            self.walk(point, sneak=True)
        self.assertTrue(world.throw_bottle((1758, 872)))
        world.update(28 / 30)
        for point in ((1987, 875), (1987, 1012)):
            self.walk(point, sneak=True)
        self.assertTrue(self.hold_in_world(60))
        self.assertIn(world.contract.stops[0], world.completed_stops)
        for point in ((2110, 1012), (2110, 987), (2608, 987)):
            self.walk(point, sneak=True)
        self.assertEqual(world.attack_count, 0)
        self.assertEqual(world.player_hp, 3)
        self.assertTrue(all(zombie.state == "patrol" for zombie in patrols))
