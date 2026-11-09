"""R2-A 공개 전투 API의 시간·판정 회귀 검사."""
import math
import unittest

from game.combat import CombatWorld, ATTACK_DURATION, ATTACK_HIT_TIME, STUN_DURATION
from game.core import Wall


class CombatTests(unittest.TestCase):
    def make_world(self, distance=60.0, angle=0.0):
        world = CombatWorld()
        world.walls = []
        world.player.x, world.player.y = 480.0, 180.0
        world.player.aim_angle = angle
        world.zombie.x = 480.0 + distance * math.cos(angle)
        world.zombie.y = 180.0 + distance * math.sin(angle)
        return world

    def test_hit_boundary_is_single_and_new_stun_is_not_consumed(self):
        world = self.make_world()
        self.assertTrue(world.start_attack())
        self.assertFalse(world.start_attack())
        world.update(0.179)
        self.assertEqual(world.zombie.hp, 5)
        self.assertFalse(world.attack.landed)
        position = (world.zombie.x, world.zombie.y)
        world.update(0.001)
        self.assertEqual(world.zombie.hp, 4)
        self.assertTrue(world.attack.landed)
        self.assertEqual(world.zombie.stun_remaining, STUN_DURATION)
        self.assertEqual((world.zombie.x, world.zombie.y), position)
        self.assertAlmostEqual(world.attack.elapsed, ATTACK_HIT_TIME)
        world.update(0.05)
        self.assertEqual(world.zombie.hp, 4)
        self.assertTrue(world.attack.landed)
        self.assertAlmostEqual(world.zombie.stun_remaining, STUN_DURATION - 0.05)
        self.assertAlmostEqual(world.zombie.x, position[0] + 4.0)
        self.assertEqual(world.zombie.y, position[1])
        self.assertFalse(world.start_attack())

    def test_stationary_front_right_profile_requires_opt_in_and_matching_facing(self):
        for facing, options, expected in (
            ("front_right", {}, (False, 0.18, 0.60)),
            ("front_right", {"stationary_front_right": True}, (True, 0.24, 0.66)),
            ("right", {"stationary_front_right": True}, (False, 0.18, 0.60)),
        ):
            with self.subTest(facing=facing, options=options):
                world = self.make_world()
                self.assertTrue(world.start_attack(facing, **options))
                attack = world.attack
                self.assertEqual((attack.stationary_front_right, attack.hit_time, attack.duration), expected)
                self.assertFalse(world.start_attack("front_right", stationary_front_right=not expected[0]))
                self.assertIs(world.attack, attack)

    def test_stationary_front_right_hits_once_and_recovers_at_066(self):
        world = self.make_world(angle=-math.pi / 4)
        world.start_attack(stationary_front_right=True)
        world.update(0.239)
        self.assertEqual(world.zombie.hp, 5)
        self.assertFalse(world.attack._hit_done)
        world.update(0.001)
        self.assertEqual((world.zombie.hp, world.zombie.stun_remaining), (4, STUN_DURATION))
        self.assertTrue(world.attack.landed)
        self.assertAlmostEqual(world.attack.elapsed, 0.24)
        world.update(0.419)
        self.assertEqual(world.zombie.hp, 4)
        self.assertAlmostEqual(world.attack.elapsed, 0.659)
        self.assertFalse(world.start_attack())
        world.update(0.001)
        self.assertIsNone(world.attack)
        self.assertTrue(world.start_attack())
        self.assertFalse(world.attack.stationary_front_right)

    def test_player_can_step_back_before_zombie_resumes_pursuit(self):
        world = self.make_world(angle=-math.pi / 4)
        origin = (world.player.x, world.player.y)
        world.start_attack(stationary_front_right=True)
        world.update(0.66, -1, 1)
        self.assertIsNone(world.attack)
        self.assertEqual((world.player.x, world.player.y), origin)
        self.assertEqual(world.zombie.hp, 4)
        zombie_position = (world.zombie.x, world.zombie.y)
        self.assertAlmostEqual(world.zombie.stun_remaining, 0.28)

        world.update(0.28, -1, 1)
        self.assertEqual((world.zombie.x, world.zombie.y), zombie_position)
        gap_before = math.dist(origin, zombie_position)
        gap_after = math.dist((world.player.x, world.player.y), zombie_position)
        self.assertAlmostEqual(gap_after - gap_before, 18.2)
        self.assertEqual(world.zombie.stun_remaining, 0.0)

        world.update(0.02)
        self.assertAlmostEqual(math.dist((world.zombie.x, world.zombie.y), zombie_position), 1.8)

    def test_stationary_profile_remains_locked_through_wall_contact_and_movement(self):
        world = CombatWorld()
        world.player.y = 310.0
        world.player.aim_angle = -math.pi / 4
        world.start_attack(stationary_front_right=True)
        world.player.aim_angle = math.pi
        world.update(0.3, 0, 1)
        self.assertEqual(world.player.y, 310.0)
        world.update(0.3, 0, -1)
        self.assertEqual(world.player.y, 310.0)
        self.assertEqual((world.attack.angle, world.attack.facing), (-math.pi / 4, "front_right"))
        self.assertTrue(world.attack.stationary_front_right)
        self.assertAlmostEqual(world.attack.elapsed, 0.6)
        world.update(0.1, 0, -1)
        self.assertIsNone(world.attack)
        self.assertAlmostEqual(world.player.y, 306.4)

    def test_stationary_front_right_miss_is_spent_at_range_or_wall(self):
        for distance, walls in ((70.0001, []), (60.0, [Wall(505, 145, 10, 25)])):
            with self.subTest(distance=distance, walls=walls):
                world = self.make_world(distance, -math.pi / 4)
                world.walls = walls
                world.zombie.stun_remaining = 0.24
                world.start_attack(stationary_front_right=True)
                world.update(0.24)
                self.assertTrue(world.attack._hit_done)
                self.assertFalse(world.attack.landed)
                self.assertEqual(world.zombie.hp, 5)
                world.walls = []
                world.update(0.15)
                self.assertLess(math.hypot(world.zombie.x - world.player.x, world.zombie.y - world.player.y), 70.0)
                self.assertEqual(world.zombie.hp, 5)
                self.assertFalse(world.attack.landed)

    def test_stationary_front_right_partitioned_hit_and_lethal_recovery(self):
        for initial_hp in (1, 5):
            positions = []
            for steps in ((0.659,), (0.0375, 0.198, 0.1195, 0.304)):
                with self.subTest(initial_hp=initial_hp, steps=steps):
                    world = self.make_world(70.0, -math.pi / 4)
                    world.zombie.hp = initial_hp
                    world.zombie.stun_remaining = 0.24
                    world.start_attack(stationary_front_right=True)
                    for dt in steps:
                        world.update(dt, 1, -1)
                    self.assertEqual(world.zombie.hp, initial_hp - 1)
                    self.assertTrue(world.attack.landed)
                    self.assertAlmostEqual(world.attack.elapsed, 0.659)
                    if initial_hp == 1:
                        self.assertEqual(world.result, "cleared")
                        self.assertEqual(world.player.x, 480.0)
                    world.update(0.001, 1, -1)
                    self.assertIsNone(world.attack)
                    positions.append((world.player.x, world.player.y, world.zombie.x, world.zombie.y,
                                      world.zombie.stun_remaining, world.player_invulnerable_remaining))
            for single, split in zip(*positions):
                self.assertAlmostEqual(single, split)

    def test_range_and_cone_boundaries_work_for_general_aim_angles(self):
        for aim in (0.0, math.pi / 2, math.pi, -math.pi / 2, 2 * math.tau + 0.4):
            for distance, offset, hp in (
                (70.0, 0.0, 4), (70.0001, 0.0, 5),
                (60.0, math.radians(30), 4), (60.0, math.radians(30.0001), 5),
                (60.0, math.radians(-30), 4), (60.0, math.radians(-30.0001), 5),
                (0.0, math.pi, 4),
            ):
                with self.subTest(aim=aim, distance=distance, offset=offset):
                    world = self.make_world(distance, aim)
                    world.zombie.stun_remaining = STUN_DURATION
                    world.zombie.x = world.player.x + distance * math.cos(aim + offset)
                    world.zombie.y = world.player.y + distance * math.sin(aim + offset)
                    world.start_attack()
                    world.update(ATTACK_HIT_TIME)
                    self.assertEqual(world.zombie.hp, hp)

    def test_wall_blocks_the_strike_segment_including_edge_contact(self):
        for wall, hp in (
            (Wall(510, 170, 10, 20), 5), (Wall(510, 180, 10, 20), 5),
            (Wall(510, 182, 10, 20), 4), (Wall(550, 170, 10, 20), 4),
            (Wall(450, 170, 10, 20), 4),
        ):
            with self.subTest(wall=wall):
                world = self.make_world()
                world.zombie.stun_remaining = STUN_DURATION
                world.walls = [wall]
                world.start_attack()
                world.update(ATTACK_HIT_TIME)
                self.assertEqual(world.zombie.hp, hp)
                self.assertTrue(world.attack._hit_done)
                self.assertIs(world.attack.landed, hp == 4)

    def test_walking_speed_follows_body_direction_including_diagonals(self):
        for angle, hint, axis, speed in (
            (0, None, (1, 0), 90),
            (math.pi, None, (1, 0), 65),
            (0, None, (0, -1), 90),
            (0, None, (-1, 1), 65),
            (-math.pi / 4, None, (-1, -1), 90),
            (math.radians(25), "right", (0, -1), 90),
        ):
            with self.subTest(angle=angle, hint=hint, axis=axis):
                world = self.make_world(400.0, angle)
                origin = (world.player.x, world.player.y)
                world.update(0.2, *axis, facing_hint=hint)
                self.assertAlmostEqual(math.dist(origin, (world.player.x, world.player.y)), speed * 0.2)

    def test_movement_rates_recovery_lock_and_attack_aim_snapshot(self):
        world = self.make_world(400.0)
        world.update(0.2, 1, 0)
        self.assertAlmostEqual(world.player.x, 498.0)
        attack_origin = world.player.x
        self.assertTrue(world.start_attack("right"))
        world.player.aim_angle = math.pi
        world.update(0.18, 1, 0)
        self.assertEqual(world.player.x, attack_origin)
        self.assertEqual((world.attack.angle, world.attack.facing), (0.0, "right"))
        self.assertFalse(world.start_attack("left"))
        world.update(0.42, 1, 0)
        self.assertEqual(world.player.x, attack_origin)
        self.assertIsNone(world.attack)
        self.assertTrue(world.start_attack("left"))
        self.assertEqual((world.attack.angle, world.attack.facing), (math.pi, "left"))
        world.update(0.8, 1, 0)
        self.assertAlmostEqual(world.player.x, 511.0)
        self.assertIsNone(world.attack)

    def test_killing_hit_stops_play_but_finishes_the_current_recovery(self):
        world = self.make_world(10.0)
        world.zombie.hp = 1
        world.start_attack()
        world.attack.elapsed = 0.179
        world.update(0.001)
        self.assertEqual((world.result, world.zombie.hp, world.player_hp), ("cleared", 0, 3))
        self.assertFalse(world.zombie.alive)
        self.assertIsNotNone(world.attack)
        self.assertTrue(world.attack.landed)
        self.assertAlmostEqual(world.attack.elapsed, 0.18)
        position = (world.player.x, world.player.y, world.zombie.x, world.zombie.y)
        self.assertFalse(world.start_attack())
        world.update(0.2, 1, 0)
        self.assertAlmostEqual(world.attack.elapsed, 0.38)
        world.update(0.22, 1, 0)
        self.assertIsNone(world.attack)
        self.assertEqual(world.result, "cleared")
        self.assertEqual((world.player.x, world.player.y, world.zombie.x, world.zombie.y), position)

    def test_zombie_chases_visible_player_at_90(self):
        world = self.make_world(200.0)
        world.update(0.5)
        self.assertAlmostEqual(world.zombie.x, 635.0)
        self.assertEqual(world.zombie.y, 180.0)

    def test_zombie_strikes_keep_one_second_immunity_and_defeat_stops_play(self):
        world = self.make_world(28.0)
        world.update(0.299)
        self.assertEqual(world.player_hp, 3)
        world.update(0.001)
        self.assertEqual(world.player_hp, 2)
        self.assertEqual(world.player_invulnerable_remaining, 1.0)
        world.update(0.8)  # The next strike occurs during the one-second immunity.
        self.assertEqual(world.player_hp, 2)
        world.update(0.8)
        self.assertEqual(world.player_hp, 1)
        self.assertEqual(world.player_invulnerable_remaining, 1.0)
        world.update(1.6)
        self.assertEqual((world.player_hp, world.result), (0, "defeated"))
        self.assertFalse(world.start_attack())
        position = (world.player.x, world.player.y, world.zombie.x, world.zombie.y)
        world.update(1.0, 1, 0)
        self.assertEqual((world.player.x, world.player.y, world.zombie.x, world.zombie.y), position)

    def test_hit_tick_keeps_full_stun_and_blocks_contact_until_expiry(self):
        world = self.make_world(10.0)
        world.start_attack()
        world.attack.elapsed = 0.179
        position = (world.zombie.x, world.zombie.y)
        world.update(0.001)
        self.assertEqual((world.zombie.hp, world.zombie.stun_remaining, world.player_hp), (4, STUN_DURATION, 3))
        self.assertEqual((world.zombie.x, world.zombie.y), position)
        world.update(STUN_DURATION - 0.001)
        self.assertEqual(world.player_hp, 3)
        self.assertAlmostEqual(world.zombie.x, position[0] + 8.0)
        self.assertEqual(world.zombie.y, position[1])
        world.update(0.001)
        self.assertEqual((world.zombie.stun_remaining, world.player_hp), (0.0, 3))
        world.update(0.3)
        self.assertEqual(world.player_hp, 2)

    def test_recoil_stops_at_wall_and_remains_inside_stun(self):
        world = self.make_world()
        world.walls = [Wall(558.0, 160.0, 20.0, 40.0)]
        world.zombie.stun_remaining = ATTACK_HIT_TIME
        world.start_attack("right")
        world.update(ATTACK_HIT_TIME)
        self.assertEqual(world.zombie.hp, 4)
        self.assertEqual(world.zombie.x, 540.0)
        world.update(0.10)
        self.assertEqual((world.zombie.x, world.zombie.y), (544.0, 180.0))
        self.assertAlmostEqual(world.zombie.stun_remaining, STUN_DURATION - 0.10)
        world.update(0.20)
        self.assertEqual((world.zombie.x, world.zombie.y), (544.0, 180.0))

    def test_existing_stun_only_blocks_its_remaining_movement_time(self):
        world = self.make_world(100.0)
        world.zombie.stun_remaining = 0.1
        world.update(0.15)
        self.assertAlmostEqual(world.zombie.x, 575.5)
        self.assertEqual(world.zombie.stun_remaining, 0.0)

    def test_player_death_cancels_a_pending_strike_and_has_result_priority(self):
        world = self.make_world(28.0)
        world.player_hp = 1
        world.player.aim_angle = math.pi
        world.update(0.2)
        world.start_attack("left")
        world.update(0.1)
        self.assertEqual((world.player_hp, world.result, world.zombie.hp), (0, "defeated", 5))
        self.assertIsNone(world.attack)
        world.update(1.0)
        self.assertEqual(world.zombie.hp, 5)
        world.zombie.hp = 0
        world.update(0.1)
        self.assertEqual(world.result, "defeated")

    def test_five_distinct_strikes_clear_the_zombie(self):
        world = self.make_world(50.0)
        for hit in range(1, 6):
            self.assertTrue(world.start_attack())
            self.assertFalse(world.attack.landed)
            world.update(0.18)
            self.assertEqual(world.zombie.hp, 5 - hit)
            self.assertTrue(world.attack.landed)
            self.assertFalse(world.start_attack())
            world.update(0.42)
            self.assertIsNone(world.attack)
        self.assertEqual(world.result, "cleared")
        self.assertEqual(world.player_hp, 3)  # Each player hit interrupts the slower zombie strike.

    def test_player_attack_movement_is_partition_independent_and_wall_safe(self):
        for count in (1, 12, 60):
            with self.subTest(count=count):
                world = self.make_world(400.0)
                world.start_attack()
                for _ in range(count):
                    world.update(ATTACK_DURATION / count, 1, 0)
                self.assertEqual(world.player.x, 480.0)
                self.assertIsNone(world.attack)
        world = CombatWorld()
        world.player.y = 300.0
        world.start_attack()
        world.update(1.0, 0, 1)
        self.assertEqual(world.player.y, 316.0)
        world.update(0.05, 0, 1)
        self.assertEqual(world.player.y, 316.0)
        self.assertFalse(world.player.moved)

    def test_reset_restores_positions_health_timers_and_wall(self):
        world = self.make_world()
        world.start_attack()
        world.update(0.2, 1, 0)
        world.player_hp = 0
        world.zombie.hp = 0
        world.player_invulnerable_remaining = 0.7
        world.walls.clear()
        world.update(0.01)
        world.reset()
        self.assertEqual((world.player.x, world.player.y), (480.0, 180.0))
        self.assertEqual((world.zombie.x, world.zombie.y, world.zombie.hp), (600.0, 100.0, 5))
        self.assertEqual((world.player_hp, world.result), (3, "playing"))
        self.assertEqual((world.zombie.stun_remaining, world.player_invulnerable_remaining), (0.0, 0.0))
        self.assertEqual(world.walls, [Wall(400, 330, 220, 60)])
        self.assertTrue(world.zombie.alive)
        self.assertIsNone(world.attack)
        self.assertTrue(world.start_attack())

    def test_invalid_or_paused_dt_does_not_advance_combat(self):
        world = self.make_world()
        world.start_attack()
        world.update(0.18)
        before = (world.player.x, world.player.y, world.zombie.x, world.zombie.y,
                  world.zombie.hp, world.attack.elapsed, world.zombie.stun_remaining,
                  world.player_hp, world.player_invulnerable_remaining, world.result)
        for dt in (0.0, -0.1, math.nan, math.inf, -math.inf, None, "0.1"):
            with self.subTest(dt=dt):
                world.update(dt, 1, 0)
                self.assertEqual((world.player.x, world.player.y, world.zombie.x, world.zombie.y,
                    world.zombie.hp, world.attack.elapsed, world.zombie.stun_remaining,
                    world.player_hp, world.player_invulnerable_remaining, world.result), before)

    def test_missed_hit_is_not_rechecked_after_target_enters_range(self):
        world = self.make_world(71.0)
        world.zombie.stun_remaining = ATTACK_HIT_TIME
        world.start_attack()
        world.update(0.18)
        self.assertEqual(world.zombie.hp, 5)
        self.assertTrue(world.attack._hit_done)
        self.assertFalse(world.attack.landed)
        world.update(0.18)
        self.assertLess(world.zombie.x - world.player.x, 70.0)
        self.assertEqual(world.zombie.hp, 5)
        self.assertFalse(world.attack.landed)

    def test_large_dt_checks_range_at_hit_time_not_at_recovery_end(self):
        for distance, hp in ((70.001, 5), (70.0, 4)):
            with self.subTest(distance=distance):
                world = self.make_world(distance)
                world.zombie.stun_remaining = STUN_DURATION
                world.start_attack()
                world.update(0.6, 1, 0)
                self.assertEqual(world.zombie.hp, hp)
                self.assertEqual(world.player.x, 480.0)

    def test_normal_dt_partitions_keep_health_timers_movement_and_recovery_consistent(self):
        cases = (
            (70.0001, 0.18, 5, 0, 3, 4, "playing"),
            (10.0, 0.18, 5, 0, 3, 4, "playing"),
            (120.0, 0.8, 5, 1, 3, 5, "playing"),
            (60.0, 0.6, 1, 1, 3, 0, "cleared"),
        )
        for distance, total, zombie_hp, axis, player_hp, target_hp, result in cases:
            reference = None
            for step in (total, 0.05, 0.016, 0.01):
                with self.subTest(distance=distance, total=total, step=step):
                    world = self.make_world(distance)
                    world.zombie.hp = zombie_hp
                    world.start_attack()
                    remaining = total
                    while remaining > 1e-12:
                        tick = min(step, remaining)
                        world.update(tick, axis, 0)
                        remaining -= tick
                    self.assertEqual((world.player_hp, world.zombie.hp, world.result),
                                     (player_hp, target_hp, result))
                    observed = (world.player.x, world.player.y, world.zombie.x, world.zombie.y,
                                world.zombie.stun_remaining, world.player_invulnerable_remaining,
                                world.attack.elapsed if world.attack is not None else -1.0)
                    if reference is None:
                        reference = observed
                    else:
                        for actual, expected in zip(observed, reference):
                            self.assertAlmostEqual(actual, expected, places=8)

    def test_huge_finite_dt_is_capped_to_ten_seconds(self):
        reference = self.make_world(10000.0)
        reference.start_attack()
        reference.update(10.0, 1, 0)
        for dt in (1000.0, 1e308):
            with self.subTest(dt=dt):
                world = self.make_world(10000.0)
                world.start_attack()
                world.update(dt, 1, 0)
                self.assertEqual((world.player_hp, world.zombie.hp, world.result),
                                 (reference.player_hp, reference.zombie.hp, reference.result))
                self.assertIsNone(world.attack)
                self.assertAlmostEqual(world.player.x, reference.player.x)
                self.assertAlmostEqual(world.zombie.x, reference.zombie.x)


if __name__ == "__main__":
    unittest.main()
