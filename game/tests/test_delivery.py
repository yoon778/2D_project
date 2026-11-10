import math
import unittest

from game.combat import ATTACK_HIT_TIME, STUN_DURATION, Zombie, ZombieAttack
from game.core import PLAYER_RADIUS, WALK_SPEED, Player, Wall, move_player
from game.delivery import DeliveryWorld, PLAYER_START, TOWN_ROADS, ZOMBIE_START, ZOMBIE_STARTS
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

    def test_both_town_routes_can_complete_delivery(self):
        main = TOWN_ROADS["main"][0]["points"]
        detour = TOWN_ROADS["main_detour"]["points"]
        routes = {
            "main road with detour": ((PLAYER_START[0], main[0][1]), *main[1:-1], *detour, main[-1]),
            "alleys": TOWN_ROADS["alleys"][0]["points"],
        }
        for name, waypoints in routes.items():
            with self.subTest(route=name):
                world = DeliveryWorld()
                self.assertEqual(tuple(waypoints[-1]), world.destination)
                self.assertTrue(world.interact())
                player = world.player
                for x, y in waypoints:
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
        road_x = road["points"][1][0]
        half_width = road["width"] / 2
        start, end = TOWN_ROADS["main_detour"]["points"][::3]
        for x in (road_x - half_width, road_x, road_x + half_width):
            with self.subTest(x=x):
                player = Player(x, start[1])
                move_player(player, 0, 1, (end[1] - start[1]) / WALK_SPEED,
                            world.walls, world_size=world.world_size)
                self.assertAlmostEqual(player.y, 730 - PLAYER_RADIUS)
        for x in (3456, world.world_size[0] - PLAYER_RADIUS):
            with self.subTest(east_margin=x):
                player = Player(x, start[1])
                move_player(player, 0, 1, (end[1] - start[1]) / WALK_SPEED,
                            world.walls, world_size=world.world_size)
                self.assertLess(player.y, 752)

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
        self.assertEqual([(zombie.x, zombie.y) for zombie in world.zombies], list(ZOMBIE_STARTS))
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
