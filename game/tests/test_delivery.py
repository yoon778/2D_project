import math
import unittest

from game.combat import ATTACK_HIT_TIME, STUN_DURATION, ZOMBIE_ATTACK_HIT_TIME, Zombie, ZombieAttack
from game.core import PLAYER_RADIUS, WALK_SPEED, Player, Wall, move_player, wall_blocks
from game.delivery import (
    BOTTLE_FLIGHT_TIME, BOTTLE_THROW_RANGE, DELIVERY_CONTRACTS, DeliveryWorld,
    PLAYER_START, TOWN_ROADS, ZOMBIE_START,
)
from game.flashlight import Flashlight


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.world = DeliveryWorld()

    def hold_e(self, dt, *, held=True, pressed=False, moving=False, damaged=False):
        return self.world.update_interaction(dt, held=held, pressed=pressed, moving=moving, damaged=damaged)

    def test_held_pickup_and_delivery_require_their_full_durations_and_new_presses(self):
        world = self.world
        self.assertFalse(self.hold_e(1.0))
        self.assertFalse(self.hold_e(0.49, pressed=True))
        self.assertEqual(world.interaction_action, "pickup")
        self.assertAlmostEqual(world.interaction_progress, 0.98)
        self.assertEqual(world.parcel, "waiting")
        self.assertTrue(self.hold_e(0.01))
        self.assertEqual((world.parcel, world.interaction_action, world.interaction_progress), ("carrying", None, 0.0))

        world.player.x, world.player.y = world.destination
        self.assertFalse(self.hold_e(1.0))
        self.assertFalse(self.hold_e(0.99, pressed=True))
        self.assertEqual(world.interaction_action, "deliver")
        self.assertIsNotNone(world.gate)
        self.assertTrue(self.hold_e(0.01))
        self.assertEqual(world.result, "delivered")
        self.assertTrue(world.just_unlocked_two_stop)
        self.assertIsNotNone(world.gate)

    def test_held_interaction_cancels_on_release_movement_damage_or_lost_target(self):
        world = self.world
        for interrupt in ({"held": False}, {"moving": True}, {"damaged": True}, {}):
            with self.subTest(interrupt=interrupt):
                world.reset()
                self.assertFalse(self.hold_e(0.4, pressed=True))
                if not interrupt:
                    world.walls.append(Wall(155, 135, 4, 40))
                self.assertFalse(self.hold_e(0.5, **interrupt))
                if not interrupt:
                    world.walls.pop()
                self.assertEqual((world.interaction_action, world.interaction_progress), (None, 0.0))
                self.assertFalse(self.hold_e(1.0))
                self.assertEqual(world.parcel, "waiting")
                self.assertTrue(self.hold_e(0.5, pressed=True))

    def test_held_gate_cancels_if_delivery_becomes_the_preferred_target(self):
        world = self.world
        self.assertTrue(world.interact())
        world.player = Player(3165, 2160)
        self.assertFalse(self.hold_e(0.65, pressed=True))
        self.assertEqual(world.interaction_action, "gate")
        world.player = Player(3155, 2218)
        self.assertTrue(world.can_open_gate())
        self.assertTrue(world.can_interact())
        self.assertFalse(self.hold_e(1.0))
        self.assertIsNone(world.interaction_action)
        self.assertIsNotNone(world.gate)
        self.assertTrue(self.hold_e(1.0, pressed=True))
        self.assertEqual(world.result, "delivered")
        self.assertIsNotNone(world.gate)

    def test_held_gate_restarts_on_fresh_press_and_only_emits_noise_on_completion(self):
        world = self.world
        world.player = Player(3165, 2160)
        guard = world.zombies[-1]
        self.assertFalse(self.hold_e(0.4, pressed=True))
        self.assertFalse(self.hold_e(0.4, pressed=True))
        self.assertAlmostEqual(world.interaction_progress, 0.4 / 0.7)
        self.assertFalse(self.hold_e(0.29))
        self.assertIsNone(guard.heard_at)
        self.assertTrue(self.hold_e(0.01))
        self.assertIsNone(world.gate)
        self.assertEqual(guard.heard_at, world.gate_position)
        guard.heard_at = None
        self.assertFalse(self.hold_e(1.0))
        self.assertIsNone(guard.heard_at)

    def test_requires_pickup_and_reaches_success_only_at_destination(self):
        world = self.world
        world.player.x, world.player.y = world.destination
        self.assertFalse(world.can_interact())
        world.interact()
        self.assertEqual((world.parcel, world.result), ("waiting", "playing"))
        world.player.x, world.player.y = PLAYER_START
        self.assertTrue(world.interact())
        self.assertEqual(world.parcel, "carrying")
        self.assertFalse(world.interact())
        world.player.x, world.player.y = world.destination
        self.assertTrue(world.interact())
        self.assertEqual((world.parcel, world.result), ("delivered", "delivered"))
        world.update(0.5, 1, 0, sprint=True)
        self.assertEqual((world.player.x, world.player.y), world.destination)
        self.assertFalse(world.interact())

    def test_delivery_stats_count_only_started_swings_and_active_play_time(self):
        world = self.world
        self.assertEqual((world.attack_count, world.elapsed_play_time, world.combat_free), (0, 0.0, True))
        self.assertTrue(world.interact())
        for dt in (0.0, -1.0, math.inf, math.nan):
            world.update(dt)
        self.assertEqual(world.elapsed_play_time, 0.0)

        self.assertTrue(world.start_attack())
        self.assertFalse(world.start_attack())
        world.update(ATTACK_HIT_TIME)
        self.assertFalse(world.attack.landed)
        self.assertEqual((world.attack_count, world.combat_free), (1, False))
        self.assertAlmostEqual(world.elapsed_play_time, ATTACK_HIT_TIME)

        world.player.x, world.player.y = world.destination
        self.assertTrue(world.interact())
        self.assertFalse(world.start_attack())
        world.update(1.0)
        self.assertEqual((world.result, world.attack_count), ("delivered", 1))
        self.assertAlmostEqual(world.elapsed_play_time, ATTACK_HIT_TIME)

        self.assertTrue(world.select_contract(0))
        self.assertEqual((world.attack_count, world.elapsed_play_time, world.combat_free), (0, 0.0, True))

    def test_damage_breaks_combat_free_status_and_lethal_hit_stops_the_clock(self):
        world = self.world
        world.player = Player(1000, 1100)
        world.walls = []
        zombie = Zombie(1010, 1100, attack=ZombieAttack(math.pi, "left"))
        world.zombies = [zombie]
        world.update(ZOMBIE_ATTACK_HIT_TIME)
        self.assertEqual((world.player_hp, world.attack_count, world.combat_free), (2, 0, False))

        world.player_hp = 1
        world.player_invulnerable_remaining = 0.0
        zombie.attack = ZombieAttack(math.pi, "left")
        world.update(1.0)
        self.assertEqual((world.result, world.player_hp), ("defeated", 0))
        self.assertAlmostEqual(world.elapsed_play_time, 2 * ZOMBIE_ATTACK_HIT_TIME)

    def test_both_contracts_can_complete_delivery_from_town_routes(self):
        main = TOWN_ROADS["main"][0]["points"]
        detour = TOWN_ROADS["main_detour"]["points"]
        alleys = TOWN_ROADS["alleys"][0]["points"]
        routes = (
            (0, (*alleys[:5], (1660, 980), (1958, 980))),
            (1, (*alleys[:7], (3190, 2080), (3230, 2080), (3230, 2227))),
            (1, ((PLAYER_START[0], main[0][1]), *main[1:-1], *detour, main[-1], (3149, 2240))),
        )
        for index, waypoints in routes:
            with self.subTest(contract=DELIVERY_CONTRACTS[index].name, waypoints=waypoints):
                world = DeliveryWorld()
                self.assertTrue(world.select_contract(index))
                self.assertTrue(world.interact())
                player = world.player
                for x, y in (*waypoints, world.destination):
                    dx, dy = x - player.x, y - player.y
                    remaining = math.hypot(dx, dy) / WALK_SPEED
                    while remaining > 0:
                        dt = min(remaining, 1.0)
                        move_player(player, dx, dy, dt, world.walls, world_size=world.world_size)
                        remaining -= dt
                    self.assertAlmostEqual(player.x, x)
                    self.assertAlmostEqual(player.y, y)
                self.assertTrue(world.interact())
                self.assertEqual(world.result, "delivered")

    def test_selecting_a_contract_resets_run_and_uses_its_own_zombies_and_destination(self):
        world = self.world
        self.assertTrue(world.interact())
        self.assertFalse(world.select_contract(-1))
        self.assertEqual(world.parcel, "carrying")
        for index, contract in enumerate(world.available_contracts):
            self.assertTrue(world.select_contract(index))
            self.assertIs(world.contract, contract)
            self.assertEqual(world.parcel, "waiting")
            self.assertEqual(world.destination, contract.destination)
            self.assertEqual(tuple((zombie.x, zombie.y) for zombie in world.zombies), contract.zombie_starts)
            appearances = [zombie.appearance for zombie in world.zombies]
            self.assertCountEqual(appearances, ["classic", "maintenance", "resident"] * 8)
            self.assertTrue(world.interact())
            world.player.x, world.player.y = DELIVERY_CONTRACTS[1 - index].destination
            self.assertFalse(world.can_interact())
            world.interact()
            self.assertEqual((world.parcel, world.result), ("carrying", "playing"))
            world.reset()
            self.assertIs(world.contract, contract)
            self.assertEqual([zombie.appearance for zombie in world.zombies], appearances)

    def test_two_stop_unlock_requires_a_single_delivery_success_and_survives_reset(self):
        for index in range(2):
            with self.subTest(contract=index):
                world = DeliveryWorld()
                self.assertEqual(world.available_contracts, DELIVERY_CONTRACTS[:2])
                self.assertFalse(world.select_contract(2))
                self.assertTrue(world.select_contract(index))
                self.assertTrue(world.interact())
                self.assertFalse(world.two_stop_unlocked)
                self.assertFalse(world.just_unlocked_two_stop)

                world.player.x, world.player.y = world.destination
                self.assertTrue(world.interact())
                self.assertTrue(world.two_stop_unlocked)
                self.assertTrue(world.just_unlocked_two_stop)
                self.assertEqual(world.available_contracts, DELIVERY_CONTRACTS)
                world.reset()
                self.assertIs(world.contract, DELIVERY_CONTRACTS[index])
                self.assertTrue(world.two_stop_unlocked)
                self.assertFalse(world.just_unlocked_two_stop)

        world = DeliveryWorld()
        self.assertTrue(world.interact())
        world.player.x, world.player.y = world.destination
        world.player_hp = 0
        self.assertFalse(world.interact())
        self.assertFalse(world.two_stop_unlocked)

    def test_two_stop_contract_accepts_both_orders_and_only_reachable_unfinished_stops(self):
        contract = DELIVERY_CONTRACTS[2]
        self.assertEqual(contract.stops, tuple(single.stops[0] for single in DELIVERY_CONTRACTS[:2]))
        for order in (contract.stops, tuple(reversed(contract.stops))):
            with self.subTest(order=order):
                world = DeliveryWorld(two_stop_unlocked=True)
                self.assertTrue(world.select_contract(2))
                self.assertEqual(world.remaining_stops, contract.stops)
                first, second = order
                world.player.x, world.player.y = first.position
                self.assertIsNone(world.interaction_target)
                world.player.x, world.player.y = PLAYER_START
                self.assertEqual(world.interaction_target, world.pickup)
                self.assertTrue(world.interact())

                x, y = first.position
                offset = 20 if first is contract.stops[1] else -20
                world.player.x, world.player.y = (x, y + offset)
                blocker = Wall(x - 1, y + offset / 2 - 1, 2, 2)
                world.walls.append(blocker)
                self.assertIsNone(world.interaction_target)
                world.walls.remove(blocker)
                self.assertEqual(world.interaction_target, first.position)
                self.assertTrue(world.interact())
                self.assertEqual((world.parcel, world.result), ("carrying", "playing"))
                self.assertEqual(world.completed_stops, {first})
                self.assertEqual(world.remaining_stops, (second,))
                self.assertIsNone(world.interaction_target)
                self.assertFalse(world.interact())

                world.player.x, world.player.y = second.position
                self.assertEqual(world.interaction_target, second.position)
                self.assertTrue(world.interact())
                self.assertEqual((world.parcel, world.result), ("delivered", "delivered"))
                self.assertEqual(world.completed_stops, set(contract.stops))
                self.assertEqual(world.remaining_stops, ())
                self.assertFalse(world.just_unlocked_two_stop)
                self.assertIsNone(world.interaction_target)
                world.reset()
                self.assertIs(world.contract, contract)
                self.assertTrue(world.two_stop_unlocked)
                self.assertEqual(world.completed_stops, set())

    def test_two_stop_contract_keeps_the_shop_horde_and_rear_patrol_within_24_zombies(self):
        world = DeliveryWorld(two_stop_unlocked=True)
        self.assertTrue(world.select_contract(2))
        positions = {(zombie.x, zombie.y) for zombie in world.zombies}
        self.assertEqual((len(world.zombies), len(positions)), (24, 24))
        lamp = Flashlight((1960, 990), 0, world.walls, world.world_size, radius=185, half_angle=math.pi)
        self.assertEqual(sum(lamp.contains(position) for position in positions), 5)
        guards = [zombie for zombie in world.zombies if zombie.state == "patrol"]
        self.assertEqual([(zombie.x, zombie.y) for zombie in guards], [(3180, 2227)])

    def test_shop_horde_is_lit_and_the_rear_house_alley_is_dark_and_narrow(self):
        world = self.world
        world.select_contract(0)
        lamps = [Flashlight(position, 0, world.walls, world.world_size, radius=185, half_angle=math.pi)
                 for position in world.streetlights]
        shop_lamp = next(lamp for lamp in lamps if lamp.origin == (1960, 990))
        self.assertTrue(shop_lamp.contains(world.destination))
        shop_zombies = [zombie for zombie in world.zombies if shop_lamp.contains((zombie.x, zombie.y))]
        self.assertEqual(len(shop_zombies), 5)
        self.assertEqual({zombie.appearance for zombie in shop_zombies}, {"classic", "maintenance", "resident"})

        world.select_contract(1)
        self.assertFalse(any(lamp.contains(point) for lamp in lamps
                             for point in (world.destination, (3230, 2227))))
        walker = Player(3000, world.destination[1])
        move_player(walker, 0, 1, 1, world.walls, world_size=world.world_size)
        self.assertEqual(walker.y, 2272 - PLAYER_RADIUS)
        move_player(walker, 0, -1, 1, world.walls, world_size=world.world_size)
        self.assertEqual(walker.y, 2200 + PLAYER_RADIUS)
        world.interact()
        world.player = Player(3180, 2150)
        move_player(world.player, 0, 1, 1, world.walls, world_size=world.world_size)
        self.assertEqual(world.player.y, 2190 - PLAYER_RADIUS)
        self.assertFalse(world.can_interact())

    def test_rear_alley_guard_patrols_both_directions_and_resets_after_contract_change(self):
        world = self.world
        guard = world.zombies[-1]
        self.assertEqual([zombie for zombie in world.zombies if zombie.state == "patrol"], [guard])
        self.assertEqual((guard.x, guard.y, guard.aim_angle), (3180, 2227, math.pi))

        world.update(1.0)
        self.assertAlmostEqual(guard.x, 3135)
        guard.stun_remaining = STUN_DURATION
        world.update(STUN_DURATION)
        self.assertAlmostEqual(guard.x, 3135)
        world.update(75 / 45)
        self.assertAlmostEqual(guard.x, 3060)
        world.update(1.0)
        self.assertAlmostEqual(guard.x, 3105)
        self.assertEqual(guard.aim_angle, 0.0)
        world.update(75 / 45)
        self.assertAlmostEqual(guard.x, 3180)
        world.update(1.0)
        self.assertAlmostEqual(guard.x, 3135)
        self.assertEqual((guard.y, guard.aim_angle), (2227, math.pi))

        world.select_contract(0)
        self.assertTrue(all(zombie.state == "idle" for zombie in world.zombies))
        world.select_contract(1)
        guard = world.zombies[-1]
        self.assertEqual((guard.state, guard.x, guard.y, guard.aim_angle), ("patrol", 3180, 2227, math.pi))

    def test_rear_alley_guard_resumes_patrol_around_fence_after_searching_noise(self):
        world = self.world
        guard = world.zombies[-1]
        sound = (3230, 2080)
        self.assertTrue(any(wall_blocks((guard.x, guard.y), sound, wall) for wall in world.walls))

        world._emit_noise(320, sound)
        world.update(0.01)
        self.assertEqual((guard.state, guard.target), ("investigate", sound))
        self.assertGreater(len(guard.investigation_route), 1)
        world.update(2.1)
        self.assertEqual((guard.state, guard.x, guard.y), ("search", *sound))
        world.update(3.0)
        self.assertEqual((guard.state, guard.target), ("patrol", None))

        world.update(7.3)
        self.assertAlmostEqual(guard.y, 2227)
        self.assertGreater(guard.x, 3060)
        self.assertLess(guard.x, 3180)
        self.assertAlmostEqual(guard.aim_angle, 0)

    def test_large_street_props_block_movement_and_cast_a_shadow(self):
        world = self.world
        for texture in ("parked-car", "dumpster", "abandoned-car"):
            with self.subTest(texture=texture):
                wall = next(wall for wall in world.walls if wall.texture == texture)
                y = wall.y + wall.depth / 2
                start = (wall.x - 40, y)
                walker = Player(*start)
                move_player(walker, 1, 0, 1, world.walls, world_size=world.world_size)
                self.assertAlmostEqual(walker.x, wall.x - PLAYER_RADIUS)
                light = Flashlight(start, 0, world.walls, world.world_size)
                self.assertFalse(light.contains((wall.x + wall.width + 18, y)))

    def test_wreck_closes_the_entire_main_road_to_direct_travel(self):
        world = self.world
        road = TOWN_ROADS["main"][0]
        self.assertEqual(road["width"], 100)
        road_x = road["points"][1][0]
        west_edge = int(road_x - road["width"] / 2)
        east_limit = int(world.world_size[0] - PLAYER_RADIUS)
        start, end = TOWN_ROADS["main_detour"]["points"][::3]
        # Check both paved edges, the gap between cars and the east map margin.
        for x in range(west_edge, east_limit + 1):
            with self.subTest(x=x):
                player = Player(x, start[1])
                move_player(player, 0, 1, (end[1] - start[1]) / WALK_SPEED,
                            world.walls, world_size=world.world_size)
                self.assertLess(player.y, end[1])

    def test_interaction_cannot_reach_through_wall(self):
        world = self.world
        world.walls = [Wall(155, 135, 4, 40)]
        self.assertFalse(world.interact())
        self.assertEqual(world.parcel, "waiting")

    def test_iron_gate_opens_once_and_unblocks_the_rear_alley(self):
        world = self.world
        self.assertTrue(world.interact())
        walls, gate = world.walls, world.gate
        approach, exit_point = (3165, 2160), (3165, 2227)
        world.player = Player(3165, 2153)
        self.assertFalse(world.interact())
        world.player = Player(*approach)
        blocker = Wall(3155, 2175, 20, 4)
        walls.append(blocker)
        self.assertFalse(world.interact())
        walls.remove(blocker)

        move_player(world.player, 0, 1, 1, walls, world_size=world.world_size)
        self.assertEqual(world.player.y, gate.y - PLAYER_RADIUS)
        self.assertTrue(wall_blocks(approach, exit_point, gate))
        guard = next(zombie for zombie in world.zombies if (zombie.x, zombie.y) == (3180, 2227))
        far = Zombie(3396, 2196, aim_angle=0.0)
        world.zombies = [guard, far]
        self.assertTrue(world.can_open_gate())
        self.assertTrue(world.interact())
        self.assertIs(world.walls, walls)
        self.assertIsNone(world.gate)
        self.assertNotIn(gate, walls)
        self.assertEqual(guard.heard_at, world.gate_position)
        self.assertIsNone(far.heard_at)
        world.update(0.001)
        self.assertEqual((guard.state, guard.target), ("investigate", world.gate_position))
        self.assertFalse(world.interact())
        self.assertIsNone(guard.heard_at)

        move_player(world.player, 0, 1, (exit_point[1] - world.player.y) / WALK_SPEED,
                    walls, world_size=world.world_size)
        self.assertAlmostEqual(world.player.y, exit_point[1])
        self.assertTrue(world.interact())
        self.assertEqual(world.result, "delivered")
        world.reset()
        self.assertIn(world.gate, world.walls)
        self.assertTrue(wall_blocks(approach, exit_point, world.gate))

    def test_delivery_takes_priority_when_both_gate_and_back_door_are_in_reach(self):
        world = self.world
        self.assertTrue(world.interact())
        world.player = Player(3155, 2218)
        self.assertTrue(world.can_open_gate())
        self.assertTrue(world.interact())
        self.assertEqual(world.result, "delivered")
        self.assertIn(world.gate, world.walls)

    def test_zero_health_overrides_delivery_and_reset_restores_run(self):
        world = self.world
        world.interact()
        world.player.x, world.player.y = world.destination
        world.player_hp = 0
        world.stamina = 2
        world.zombie.hp = 0
        self.assertFalse(world.interact())
        self.assertEqual(world.result, "defeated")
        world.reset()
        self.assertEqual((world.player_hp, world.stamina), (3, 100))
        self.assertEqual((world.result, world.parcel), ("playing", "waiting"))
        self.assertEqual((world.player.x, world.player.y), PLAYER_START)
        self.assertEqual((world.zombie.x, world.zombie.y, world.zombie.hp), (*ZOMBIE_START, 5))
        self.assertEqual((world.zombie.state, world.zombie.target), ("idle", None))
        self.assertEqual(tuple((zombie.x, zombie.y) for zombie in world.zombies), world.contract.zombie_starts)
        self.assertTrue(all(zombie.alive for zombie in world.zombies))

    def test_killing_zombie_leaves_delivery_active_and_corpse_cannot_be_hit(self):
        world = self.world
        world.player.aim_angle = 0
        world.zombie.x, world.zombie.y = (175, 145)
        world.zombie.hp = 1
        self.assertTrue(world.start_attack())
        world.update(0.6)
        self.assertEqual((world.zombie.hp, world.result), (0, "playing"))
        self.assertTrue(world.start_attack())
        world.update(0.6)
        self.assertEqual(world.zombie.hp, 0)
        self.assertTrue(world.interact())

    def test_one_swing_hits_each_eligible_zombie_once_at_the_same_time(self):
        world = self.world
        world.player.x, world.player.y, world.player.aim_angle = (1000, 1100, 0.0)
        world.walls = [Wall(1020, 1110, 5, 25)]
        farther = Zombie(1062, 1087, attack=ZombieAttack(math.pi, "left"))
        nearer = Zombie(1042, 1101, attack=ZombieAttack(math.pi, "left"))
        excluded = [
            Zombie(1100, 1100, stun_remaining=STUN_DURATION),  # Out of reach
            Zombie(1030, 1054, stun_remaining=STUN_DURATION),  # Outside the swing angle
            Zombie(1050, 1129, stun_remaining=STUN_DURATION),  # Behind the wall
            Zombie(1035, 1094, hp=0),
        ]
        world.zombies = [farther, *excluded, nearer]
        self.assertTrue(world.start_attack())
        world.update(ATTACK_HIT_TIME - 0.01)
        self.assertEqual((farther.hp, nearer.hp), (5, 5))
        self.assertIsNotNone(farther.attack)
        self.assertIsNotNone(nearer.attack)

        world.update(0.01)
        self.assertTrue(world.attack.landed)
        self.assertEqual(len(world.attack.hit_targets), 2)
        self.assertIs(world.attack.hit_targets[0], farther)
        self.assertIs(world.attack.hit_targets[1], nearer)
        for zombie in (farther, nearer):
            self.assertEqual(zombie.hp, 4)
            self.assertEqual(zombie.stun_remaining, STUN_DURATION)
            self.assertIsNone(zombie.attack)

        world.update(0.05)
        self.assertEqual([zombie.hp for zombie in world.zombies], [4, 5, 5, 5, 0, 4])

    def test_noise_is_investigated_independently_across_a_wall(self):
        world = self.world
        world.player.x, world.player.y = (975, 1000)
        world.walls = [Wall(1010, 930, 40, 160)]
        south, north, distant = Zombie(1100, 950), Zombie(1120, 1080), Zombie(1610, 1050)
        world.zombies = [south, north, distant]
        world.start_attack()
        world.update(0.05)
        self.assertEqual([zombie.state for zombie in world.zombies], ["investigate", "investigate", "idle"])
        self.assertEqual(south.target, north.target)
        self.assertNotEqual(south.investigation_route[0], north.investigation_route[0])

    def test_quiet_steps_do_not_alert_a_zombie_outside_their_reduced_range(self):
        for sneak, expected in ((True, "idle"), (False, "investigate")):
            with self.subTest(sneak=sneak):
                world = DeliveryWorld()
                world.player = Player(150, 100, 0)
                world.walls = [Wall(110, 130, 220, 5)]
                world.zombies = [Zombie(186, 160)]
                world.update(0.8, 1, 0, sneak=sneak)
                self.assertEqual(world.zombie.state, expected)
                if sneak:
                    self.assertIsNone(world.zombie.target)

    def test_quiet_step_can_alert_a_close_zombie_behind_a_wall(self):
        world = self.world
        world.player = Player(150, 100, 0)
        world.walls = [Wall(110, 117, 220, 4)]
        world.zombies = [Zombie(186, 139), Zombie(186, 141)]
        world.update(35 / 55, 1, 0, sneak=True)
        self.assertEqual([zombie.state for zombie in world.zombies], ["idle", "idle"])
        world.update(1 / 55, 1, 0, sneak=True)
        self.assertEqual([zombie.state for zombie in world.zombies], ["investigate", "idle"])
        self.assertAlmostEqual(world.zombie.target[0], 186)
        self.assertEqual(world.zombie.target[1], 100)

    def test_attack_noise_reaches_400_pixels_across_a_wall(self):
        world = self.world
        world.player = Player(975, 1000)
        world.walls = [Wall(1010, 930, 40, 160)]
        world.zombies = [Zombie(1375, 1000), Zombie(1376, 1000)]
        self.assertTrue(world.start_attack())
        world.update(0.01)
        self.assertEqual([zombie.state for zombie in world.zombies], ["investigate", "idle"])
        self.assertEqual(world.zombie.target, (975, 1000))

    def test_sprint_collision_alarms_each_car_once_and_reset_rearms_it(self):
        world = self.world
        for _ in range(2):
            cars = [wall for wall in world.walls if wall.texture in ("parked-car", "abandoned-car")]
            self.assertEqual(len(cars), 5)
            world.walls = cars
            world.zombies = []
            for car in cars:
                with self.subTest(car=(car.x, car.y)):
                    x = car.x + car.width / 2
                    world.player = Player(x, car.y - 20, math.pi / 2)
                    world.update(0.04, 0, 1, sprint=True)
                    self.assertEqual(world.vehicle_alarm, (x, car.y - PLAYER_RADIUS))
                    world.update(0.04, 0, 1, sprint=True)
                    self.assertIsNone(world.vehicle_alarm)
            world.reset()
            self.assertIsNone(world.vehicle_alarm)

    def test_vehicle_alarm_reaches_zombies_behind_the_car_up_to_520_pixels(self):
        world = self.world
        car = next(wall for wall in world.walls if wall.texture == "parked-car")
        world.walls = [car]
        world.player = Player(350, 120, 0)
        source = (car.x - PLAYER_RADIUS, 120)
        world.zombies = [Zombie(source[0] + distance, 120) for distance in (520, 521)]
        world.update(0.04, 1, 0, sprint=True)
        self.assertEqual(world.vehicle_alarm, source)
        self.assertEqual([zombie.state for zombie in world.zombies], ["investigate", "idle"])
        self.assertEqual(world.zombie.target, source)
        self.assertFalse(world._player_line_clear(world.zombie))

    def test_vehicle_alarm_requires_a_blocked_sprint_or_a_bat_hit(self):
        for case in ("walk", "sneak", "backstep", "exhausted", "parallel", "no input", "wall first"):
            with self.subTest(case=case):
                world = DeliveryWorld()
                car = next(wall for wall in world.walls if wall.texture == "parked-car")
                world.walls = [car]
                world.zombies = []
                world.player = Player(350, 120, math.pi if case == "backstep" else 0)
                axis = (1, 0)
                if case == "exhausted":
                    world.stamina, world._sprint_exhausted = 0, True
                elif case == "parallel":
                    world.player = Player(car.x - PLAYER_RADIUS, 120, math.pi / 2)
                    axis = (0, 1)
                elif case == "no input":
                    axis = (0, 0)
                elif case == "wall first":
                    world.walls.insert(0, Wall(366, 99, 2, 44))
                world.update(0.15, *axis, sprint=case != "walk", sneak=case == "sneak")
                self.assertIsNone(world.vehicle_alarm)

    def test_bat_checks_vehicle_range_and_cover_on_the_locked_impact_ray(self):
        for case in ("hit", "short", "off aim", "wall first"):
            with self.subTest(case=case):
                world = DeliveryWorld()
                car = next(wall for wall in world.walls if wall.texture == "parked-car")
                world.walls = [car]
                world.zombies = []
                angle = math.pi / 2 if case == "off aim" else 0
                world.player = Player(299 if case == "short" else 300, 120,
                                      angle)
                if case == "wall first":
                    world.walls.append(Wall(350, 100, 5, 40))
                self.assertTrue(world.start_attack(stationary_front_right=True))
                world.player.aim_angle = math.pi
                world.update(0.239)
                self.assertIsNone(world.vehicle_alarm)
                world.update(0.001)
                self.assertEqual(world.vehicle_alarm, (356, 120) if case == "hit" else None)
                self.assertFalse(world.attack.landed)
                world.update(0.42)
                world.player.aim_angle = angle
                self.assertTrue(world.start_attack())
                world.update(ATTACK_HIT_TIME)
                self.assertIsNone(world.vehicle_alarm)

    def test_sneaking_is_55_pixels_per_second_in_all_directions_and_still_visible(self):
        for axis_x, axis_y in ((1, 0), (-1, 0), (-1, 1)):
            with self.subTest(direction=(axis_x, axis_y)):
                world = DeliveryWorld()
                world.player = Player(500, 500, 0)
                world.walls = []
                world.zombies = [Zombie(500, 670, aim_angle=-math.pi / 2)]
                world.update(1.0, axis_x, axis_y, sprint=True, sneak=True)
                self.assertAlmostEqual(math.dist((500, 500), (world.player.x, world.player.y)), 55)
                self.assertTrue(world.sneaking)
                self.assertFalse(world.sprinting)
                self.assertIsNone(world.sprint_step)
                self.assertEqual(world.stamina, 100)
                self.assertEqual(world.zombie.state, "chase")
                world.update(0, axis_x, axis_y, sneak=True)
                self.assertFalse(world.sneaking)

    def test_zombie_uses_facing_range_and_walls_to_discover_player(self):
        cases = (
            (60, 230, False, "chase"),
            (-60, 230, False, "chase"),
            (60.1, 230, False, "idle"),
            (0, 230.1, False, "idle"),
            (180, 32, False, "chase"),
            (180, 32.1, False, "idle"),
            (180, 32, True, "idle"),
        )
        for angle, distance, blocked, expected in cases:
            with self.subTest(angle=angle, distance=distance, blocked=blocked):
                world = DeliveryWorld()
                angle = math.radians(angle)
                world.player = Player(500 + distance * math.cos(angle), 500 + distance * math.sin(angle))
                world.zombies = [Zombie(500, 500, aim_angle=0)]
                world.walls = [Wall(484, 490, 4, 20)] if blocked else []
                world.update(0.001)
                self.assertEqual(world.zombie.state, expected)

    def test_existing_chase_ignores_facing_but_reacquisition_needs_it(self):
        world = self.world
        world.player = Player(400, 500)
        world.zombies = [Zombie(500, 500, aim_angle=0, state="chase", target=(400, 500))]
        world.walls = []
        world.update(0.001)
        self.assertEqual(world.zombie.state, "chase")

        world.walls = [Wall(448, 490, 4, 20)]
        world.update(0.001)
        self.assertEqual(world.zombie.state, "investigate")

        world.walls.clear()
        world.zombie.aim_angle = 0
        world.update(0.001)
        self.assertEqual(world.zombie.state, "investigate")
        world.zombie.aim_angle = math.pi
        world.update(0.001)
        self.assertEqual(world.zombie.state, "chase")

    def test_bottle_turns_guard_away_from_sneaking_player(self):
        world = self.world
        world.player = Player(500, 500)
        world.zombies = [Zombie(650, 500, aim_angle=0)]
        world.walls = []
        world.bottle_pickups = [(500, 500)]
        self.assertTrue(world.pick_up_bottle())

        world.update(0.5, 0, 1, sneak=True)
        self.assertEqual(world.zombie.state, "idle")
        self.assertTrue(world.throw_bottle((780, 640)))
        world.update(BOTTLE_FLIGHT_TIME + 0.05, 0, 1, sneak=True)

        self.assertEqual((world.zombie.state, world.zombie.target), ("investigate", (780, 640)))
        self.assertAlmostEqual(world.zombie.aim_angle, math.atan2(140, 130))

    def test_quiet_distance_is_not_carried_into_the_next_audible_step(self):
        world = self.world
        world.player = Player(150, 100, 0)
        world.walls = [Wall(110, 130, 220, 5)]
        world.zombies = [Zombie(240, 160)]
        world.update(20 / WALK_SPEED, 1, 0)
        world.update(1, 1, 0, sneak=True)
        world.update(15 / WALK_SPEED, 1, 0)
        self.assertEqual(world.zombie.state, "idle")
        world.update(1 / WALK_SPEED, 1, 0)
        self.assertEqual(world.zombie.state, "investigate")
        self.assertAlmostEqual(world.zombie.target[0], 241)

    def test_bottle_pickup_throw_limits_and_reset(self):
        world = self.world
        bottle = world.nearby_bottle
        self.assertIsNotNone(bottle)
        original_walls = world.walls
        world.walls = [Wall(155, 120, 4, 30)]
        self.assertFalse(world.pick_up_bottle())
        world.walls = original_walls
        self.assertFalse(world.can_throw_bottle((450, 145)))
        self.assertFalse(world.throw_bottle((450, 145)))
        self.assertTrue(world.interact())
        self.assertTrue(world.pick_up_bottle())
        self.assertEqual(world.parcel, "carrying")
        self.assertNotIn(bottle, world.bottle_pickups)
        self.assertFalse(world.pick_up_bottle())
        self.assertFalse(world.can_throw_bottle(PLAYER_START))
        self.assertFalse(world.throw_bottle(PLAYER_START))

        world.walls = [Wall(220, 120, 50, 100)]
        self.assertTrue(world.can_throw_bottle((600, 145)))
        self.assertTrue(world.has_bottle)
        self.assertIsNone(world.bottle_flight)
        self.assertTrue(world.throw_bottle((600, 145)))
        self.assertFalse(world.has_bottle)
        self.assertEqual(world.bottle_flight.origin, PLAYER_START)
        self.assertAlmostEqual(world.bottle_flight.destination[0], 220 - PLAYER_RADIUS, places=3)
        self.assertFalse(world.throw_bottle((600, 145)))
        world.update(0)
        self.assertEqual(world.bottle_flight.progress, 0)
        self.assertIsNone(world.bottle_impact)

        world.reset()
        self.assertIsNone(world.bottle_flight)
        self.assertIsNone(world.bottle_impact)
        self.assertFalse(world.has_bottle)
        self.assertIn(bottle, world.bottle_pickups)
        self.assertTrue(world.pick_up_bottle())
        world.walls = []
        self.assertTrue(world.throw_bottle((900, 145)))
        self.assertEqual(math.dist(PLAYER_START, world.bottle_flight.destination), BOTTLE_THROW_RANGE)

    def test_bottle_landing_draws_a_zombie_around_the_first_alley_wall_once(self):
        world = self.world
        self.assertTrue(world.pick_up_bottle())
        world.player.x, world.player.y = (266, 194)
        zombie = next(zombie for zombie in world.zombies if (zombie.x, zombie.y) == (485, 475))
        distant = Zombie(900, 600)
        world.zombies = [zombie, distant]
        landing = (565, 194)
        start = (zombie.x, zombie.y)
        self.assertTrue(any(wall_blocks(start, landing, wall) for wall in world.walls))
        self.assertFalse(world._player_line_clear(zombie))
        self.assertTrue(world.throw_bottle(landing))

        world.update(BOTTLE_FLIGHT_TIME - .02)
        self.assertEqual(zombie.state, "idle")
        self.assertIsNone(world.bottle_impact)
        world.update(.02)
        self.assertEqual(world.bottle_impact, landing)
        self.assertIsNone(world.bottle_flight)
        self.assertEqual((zombie.state, zombie.target), ("investigate", landing))
        self.assertEqual(distant.state, "idle")
        self.assertTrue(any(x > 585 for x, _ in zombie.investigation_route))

        world.update(.01)
        self.assertIsNone(world.bottle_impact)
        for _ in range(20):
            if zombie.state == "search":
                break
            world.update(.25)
        self.assertEqual(zombie.state, "search")
        self.assertAlmostEqual(math.dist((zombie.x, zombie.y), landing), 0, places=6)
        self.assertEqual(zombie.hp, 5)

    def test_delivery_sprint_opens_distance_from_a_chasing_zombie(self):
        world = self.world
        world.player.aim_angle = 0.0
        zombie = Zombie(world.player.x - 90, world.player.y)
        world.zombies = [zombie]
        world.update(1.0, 1, 0, sprint=True)
        self.assertEqual(zombie.state, "chase")
        self.assertAlmostEqual(world.player.x - PLAYER_START[0], 210.0)
        self.assertAlmostEqual(world.player.x - zombie.x, 210.0)
        self.assertLess(world.stamina, 100.0)
