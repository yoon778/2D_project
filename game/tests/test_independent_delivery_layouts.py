import unittest

from delivery import BUS_BROADCAST_COOLDOWN, PLAYABLE_CONTRACTS, SHOP_ROUND_TRIP, TOWN_ROADS, DeliveryWorld
from core import wall_blocks
from zombie_navigation import can_walk_direct, find_route


class IndependentDeliveryLayoutsTests(unittest.TestCase):
    def select(self, number):
        world = DeliveryWorld()
        self.assertTrue(world.select_playable_contract(number))
        return world

    def hold(self, world, action, duration):
        self.assertEqual(world.interaction_candidate, action)
        self.assertFalse(world.update_interaction(duration - 0.01, held=True, pressed=True,
                                                  moving=False, damaged=False))
        self.assertTrue(world.update_interaction(0.01, held=True, pressed=False, moving=False, damaged=False))

    def test_active_contract_numbers_and_layout_reset(self):
        self.assertEqual(tuple(PLAYABLE_CONTRACTS), (1, 2, 4))
        world = self.select(1)
        first = world.contract.layout
        self.assertFalse(world.select_playable_contract(3))
        self.assertIs(world.contract.layout, first)
        self.assertTrue(world.select_playable_contract(2))
        second = world.contract.layout
        self.assertNotEqual(first.roads, second.roads)
        self.assertNotEqual(first.walls, second.walls)
        self.assertNotEqual(first.ground_file, second.ground_file)
        self.assertEqual(world.world_size, (2000, 1350))
        self.assertIs(world.roads, second.roads)
        self.assertIsNone(world.gate)
        self.assertTrue(world.select_playable_contract(4))
        self.assertIs(world.contract, SHOP_ROUND_TRIP)
        self.assertIs(world.roads, TOWN_ROADS)
        self.assertEqual(world.world_size, (3600, 2400))
        self.assertIsNotNone(world.bridge_puzzle)

    def test_new_truck_lane_and_all_delivery_orders(self):
        for number in (1, 2):
            for reverse in (False, True):
                with self.subTest(contract=number, reverse=reverse):
                    world = self.select(number)
                    layout = world.contract.layout
                    x, y, width, depth = world.truck_footprint
                    self.assertLessEqual(x + width, world.world_size[0])
                    self.assertTrue(world.skip_route_sequence())
                    parked_x = world.truck_wall.x
                    for wall in layout.walls:
                        overlaps_lane = (wall.x < x + width and wall.x + wall.width > 2 * parked_x - x
                                         and wall.y < y + depth and wall.y + wall.depth > y)
                        self.assertFalse(overlaps_lane)
                    self.hold(world, "pickup", 0.50)
                    self.assertFalse(world.can_board_truck())
                    stops = world.contract.stops[::-1] if reverse else world.contract.stops
                    self.assertEqual(len(stops), 2)
                    for stop in stops:
                        self.assertTrue(can_walk_direct(stop.position, stop.position, world.walls))
                        world.player.x, world.player.y = stop.position
                        self.hold(world, "deliver", 1.00)
                    self.assertEqual(world.mission_phase, "returning")
                    self.assertEqual(world.result, "playing")
                    world.player.x, world.player.y = world.contract.truck_door_position
                    self.hold(world, "board_truck", 0.70)
                    self.assertEqual(world.mission_phase, "boarding")
                    self.assertTrue(world.advance_route_sequence(2.00))
                    self.assertEqual(world.result, "delivered")
                    self.assertFalse(world.just_unlocked_two_stop)
                    world.reset()
                    self.assertEqual(world.mission_phase, "arriving")
                    self.assertFalse(world.completed_stops)

    def test_repair_gate_opens_a_shortcut_and_emits_noise_across_the_partition(self):
        world = self.select(1)
        world.skip_route_sequence()
        self.hold(world, "pickup", 0.50)
        origin, beyond_gate = (980, 575), (980, 650)
        self.assertFalse(can_walk_direct(origin, beyond_gate, world.walls))
        self.assertTrue(find_route(origin, beyond_gate, world.walls, world.world_size))
        detour, = world.contract.layout.detour_routes
        self.assertTrue(all(can_walk_direct(a, b, world.walls) for a, b in zip(detour, detour[1:])))
        world.player.x, world.player.y = origin
        guard = world.zombies[0]
        self.assertTrue(any(wall is not world.gate and wall_blocks((guard.x, guard.y), origin, wall)
                            for wall in world.walls))
        self.hold(world, "gate", 0.70)
        self.assertIsNone(world.gate)
        self.assertTrue(can_walk_direct(origin, beyond_gate, world.walls))
        self.assertEqual(guard.heard_at, world.gate_position)
        world.update(0.02)
        self.assertEqual(guard.state, "investigate")
        self.assertFalse(world.can_open_gate())

    def test_warehouse_broadcast_draws_guards_off_the_lane_and_preserves_detour(self):
        world = self.select(2)
        world.skip_route_sequence()
        self.hold(world, "pickup", 0.50)
        world.player.x, world.player.y = 790, 457
        speaker = world.bus_speaker_position
        self.assertTrue(any(wall_blocks(world.bus_switch_position, speaker, wall) for wall in world.walls))
        guard = world.zombies[0]
        start_x = guard.x
        self.assertTrue(any(wall_blocks((guard.x, guard.y), speaker, wall) for wall in world.walls))
        self.hold(world, "bus_broadcast", 0.70)
        self.assertEqual(world.bus_broadcast_source, speaker)
        self.assertEqual(world.bus_broadcast_cooldown, BUS_BROADCAST_COOLDOWN)
        self.assertEqual(guard.heard_at, speaker)
        self.assertFalse(world.can_start_bus_broadcast())
        world.update(1.00)
        self.assertEqual(guard.state, "investigate")
        self.assertGreater(guard.x, start_x)
        detour, = world.contract.layout.detour_routes
        self.assertTrue(all(can_walk_direct(a, b, world.walls) for a, b in zip(detour, detour[1:])))
