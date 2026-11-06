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
        position = (world.zombie.x, world.zombie.y)
        world.update(0.001)
        self.assertEqual(world.zombie.hp, 4)
        self.assertEqual(world.zombie.stun_remaining, STUN_DURATION)
        self.assertEqual((world.zombie.x, world.zombie.y), position)
        self.assertAlmostEqual(world.attack.elapsed, ATTACK_HIT_TIME)
        world.update(0.05)
        self.assertEqual(world.zombie.hp, 4)
        self.assertAlmostEqual(world.zombie.stun_remaining, 0.35)
        self.assertEqual((world.zombie.x, world.zombie.y), position)
        self.assertFalse(world.start_attack())

    def test_range_and_cone_boundaries_work_for_general_aim_angles(self):
        for aim in (0.0, math.pi / 2, math.pi, -math.pi / 2, 2 * math.tau + 0.4):
            for distance, offset, hp in (
                (80.0, 0.0, 4), (80.0001, 0.0, 5),
                (60.0, math.radians(50), 4), (60.0, math.radians(50.0001), 5),
                (60.0, math.radians(-50), 4), (60.0, math.radians(-50.0001), 5),
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

    def test_movement_rates_recovery_lock_and_attack_aim_snapshot(self):
        world = self.make_world(400.0)
        world.update(0.2, 1, 0)
        self.assertAlmostEqual(world.player.x, 498.0)
        self.assertTrue(world.start_attack("right"))
        world.player.aim_angle = math.pi
        world.update(0.18, 1, 0)
        self.assertAlmostEqual(world.player.x, 508.8)
        self.assertEqual((world.attack.angle, world.attack.facing), (0.0, "right"))
        self.assertFalse(world.start_attack("left"))
        world.update(0.42, 1, 0)
        self.assertAlmostEqual(world.player.x, 534.0)
        self.assertIsNone(world.attack)
        self.assertTrue(world.start_attack("left"))
        self.assertEqual((world.attack.angle, world.attack.facing), (math.pi, "left"))
        world.update(0.8, 1, 0)
        self.assertAlmostEqual(world.player.x, 588.0)
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
        self.assertAlmostEqual(world.attack.elapsed, 0.18)
        position = (world.player.x, world.player.y, world.zombie.x, world.zombie.y)
        self.assertFalse(world.start_attack())
        world.update(0.2, 1, 0)
        self.assertAlmostEqual(world.attack.elapsed, 0.38)
        world.update(0.22, 1, 0)
        self.assertIsNone(world.attack)
        self.assertEqual(world.result, "cleared")
        self.assertEqual((world.player.x, world.player.y, world.zombie.x, world.zombie.y), position)

    def test_zombie_chases_at_90_and_stops_at_existing_wall(self):
        world = self.make_world(200.0)
        world.update(0.5)
        self.assertAlmostEqual(world.zombie.x, 635.0)
        self.assertEqual(world.zombie.y, 180.0)
        world = CombatWorld()
        world.player.x, world.player.y = 300.0, 360.0
        world.zombie.x, world.zombie.y = 650.0, 360.0
        world.update(0.5)
        self.assertEqual((world.zombie.x, world.zombie.y), (634.0, 360.0))
        world.update(0.5)
        self.assertEqual((world.zombie.x, world.zombie.y), (634.0, 360.0))
        self.assertEqual(world.player_hp, 3)

    def test_contact_damage_has_one_second_immunity_and_defeat_stops_play(self):
        world = self.make_world(28.0)
        world.update(0.001)
        self.assertEqual(world.player_hp, 2)
        self.assertEqual(world.player_invulnerable_remaining, 1.0)
        world.update(0.999)
        self.assertEqual(world.player_hp, 2)
        world.update(0.001)
        self.assertEqual(world.player_hp, 1)
        self.assertEqual(world.player_invulnerable_remaining, 1.0)
        world.update(1.0)
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
        self.assertEqual((world.zombie.hp, world.zombie.stun_remaining, world.player_hp), (4, 0.4, 3))
        self.assertEqual((world.zombie.x, world.zombie.y), position)
        world.update(0.399)
        self.assertEqual(world.player_hp, 3)
        self.assertEqual((world.zombie.x, world.zombie.y), position)
        world.update(0.001)
        self.assertEqual((world.zombie.stun_remaining, world.player_hp), (0.0, 2))

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
        world.start_attack("left")
        world.update(0.05)
        self.assertEqual((world.player_hp, world.result, world.zombie.hp), (0, "defeated", 5))
        self.assertIsNone(world.attack)
        world.update(1.0)
        self.assertEqual(world.zombie.hp, 5)
        world.zombie.hp = 0
        world.update(0.1)
        self.assertEqual(world.result, "defeated")

    def test_five_distinct_strikes_clear_the_zombie(self):
        world = self.make_world()
        for hit in range(1, 6):
            self.assertTrue(world.start_attack())
            world.update(0.18)
            self.assertEqual(world.zombie.hp, 5 - hit)
            self.assertFalse(world.start_attack())
            world.update(0.42)
            self.assertIsNone(world.attack)
        self.assertEqual(world.result, "cleared")
        self.assertGreater(world.player_hp, 0)  # 준비 중 접촉 피해는 허용한다.

    def test_player_attack_movement_is_partition_independent_and_wall_safe(self):
        for count in (1, 12, 60):
            with self.subTest(count=count):
                world = self.make_world(400.0)
                world.start_attack()
                for _ in range(count):
                    world.update(ATTACK_DURATION / count, 1, 0)
                self.assertAlmostEqual(world.player.x, 516.0)
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
        world = self.make_world(81.0)
        world.zombie.stun_remaining = ATTACK_HIT_TIME
        world.start_attack()
        world.update(0.18)
        self.assertEqual(world.zombie.hp, 5)
        world.update(0.18)
        self.assertLess(world.zombie.x - world.player.x, 80.0)
        self.assertEqual(world.zombie.hp, 5)

    def test_large_dt_checks_range_at_hit_time_not_at_recovery_end(self):
        for distance, hp in ((100.0, 5), (90.0, 4)):
            with self.subTest(distance=distance):
                world = self.make_world(distance)
                world.zombie.stun_remaining = STUN_DURATION
                world.start_attack()
                world.update(0.6, 1, 0)
                self.assertEqual(world.zombie.hp, hp)
                self.assertAlmostEqual(world.player.x, 516.0)

    def test_normal_dt_partitions_keep_health_timers_movement_and_recovery_consistent(self):
        cases = (
            (80.0001, 0.18, 5, 0, 3, 4, "playing"),
            (10.0, 0.18, 5, 0, 2, 4, "playing"),
            (120.0, 0.8, 5, 1, 2, 5, "playing"),
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
