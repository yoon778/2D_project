import math
import unittest

from game.combat import ATTACK_HIT_TIME, STUN_DURATION, Zombie, ZombieAttack
from game.core import PLAYER_RADIUS, WALK_SPEED, Player, Wall, move_player, wall_blocks
from game.delivery import (
    BOTTLE_FLIGHT_TIME, BOTTLE_THROW_RANGE, DELIVERY_CONTRACTS, DeliveryWorld,
    PLAYER_START, TOWN_ROADS, ZOMBIE_START,
)
from game.flashlight import Flashlight


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.world = DeliveryWorld()

    def test_requires_pickup_and_reaches_success_only_at_destination(self):
        world = self.world
        world.player.x, world.player.y = world.destination
        self.assertFalse(world.interact())
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
        for index, contract in enumerate(DELIVERY_CONTRACTS):
            self.assertTrue(world.select_contract(index))
            self.assertIs(world.contract, contract)
            self.assertEqual(world.parcel, "waiting")
            self.assertEqual(world.destination, contract.destination)
            self.assertEqual(tuple((zombie.x, zombie.y) for zombie in world.zombies), contract.zombie_starts)
            self.assertTrue(world.interact())
            world.player.x, world.player.y = DELIVERY_CONTRACTS[1 - index].destination
            self.assertFalse(world.interact())
            world.reset()
            self.assertIs(world.contract, contract)

    def test_shop_horde_is_lit_and_the_rear_house_alley_is_dark_and_narrow(self):
        world = self.world
        world.select_contract(0)
        lamps = [Flashlight(position, 0, world.walls, world.world_size, radius=185, half_angle=math.pi)
                 for position in world.streetlights]
        shop_lamp = next(lamp for lamp in lamps if lamp.origin == (1960, 990))
        self.assertTrue(shop_lamp.contains(world.destination))
        self.assertEqual(sum(shop_lamp.contains((zombie.x, zombie.y)) for zombie in world.zombies), 5)

        world.select_contract(1)
        self.assertFalse(any(lamp.contains(point) for lamp in lamps
                             for point in (world.destination, (3230, 2227))))
        walker = Player(3000, world.destination[1])
        move_player(walker, 0, 1, 1, world.walls, world_size=world.world_size)
        self.assertEqual(walker.y, 2260 - PLAYER_RADIUS)
        move_player(walker, 0, -1, 1, world.walls, world_size=world.world_size)
        self.assertEqual(walker.y, 2200 + PLAYER_RADIUS)
        world.interact()
        world.player = Player(3180, 2150)
        move_player(world.player, 0, 1, 1, world.walls, world_size=world.world_size)
        self.assertEqual(world.player.y, 2190 - PLAYER_RADIUS)
        self.assertFalse(world.can_interact())

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

    def test_quiet_steps_do_not_alert_a_zombie_behind_a_wall(self):
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

    def test_sneaking_is_55_pixels_per_second_in_all_directions_and_still_visible(self):
        for axis_x, axis_y in ((1, 0), (-1, 0), (-1, 1)):
            with self.subTest(direction=(axis_x, axis_y)):
                world = DeliveryWorld()
                world.player = Player(500, 500, 0)
                world.walls = []
                world.zombies = [Zombie(500, 670)]
                world.update(1.0, axis_x, axis_y, sprint=True, sneak=True)
                self.assertAlmostEqual(math.dist((500, 500), (world.player.x, world.player.y)), 55)
                self.assertTrue(world.sneaking)
                self.assertFalse(world.sprinting)
                self.assertIsNone(world.sprint_step)
                self.assertEqual(world.stamina, 100)
                self.assertEqual(world.zombie.state, "chase")
                world.update(0, axis_x, axis_y, sneak=True)
                self.assertFalse(world.sneaking)

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
        self.assertFalse(world.throw_bottle((450, 145)))
        self.assertTrue(world.interact())
        self.assertTrue(world.pick_up_bottle())
        self.assertEqual(world.parcel, "carrying")
        self.assertNotIn(bottle, world.bottle_pickups)
        self.assertFalse(world.pick_up_bottle())
        self.assertFalse(world.throw_bottle(PLAYER_START))

        world.walls = [Wall(220, 120, 50, 100)]
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
