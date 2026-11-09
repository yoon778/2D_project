"""R2-AW 실제 전투 이동 변위와 기존 보행 위상의 연결 계약."""
import math
import unittest

from game.combat import CombatWorld, STUN_DURATION
from game.core import Wall
from game.locomotion import Locomotion


class AttackWalkLogicTests(unittest.TestCase):
    def make_world(self):
        world = CombatWorld()
        world.walls = []
        world.player.aim_angle = -math.pi / 4
        world.zombie.x, world.zombie.y = 900.0, 650.0
        return world

    def advance(self, world, motion, dt, axis=(0, 0)):
        before = (world.player.x, world.player.y)
        world.update(dt, *axis)
        dx, dy = world.player.x - before[0], world.player.y - before[1]
        angle = world.attack.angle if world.attack is not None else world.player.aim_angle
        motion.update(angle, dx, dy)
        return math.hypot(dx, dy)

    def test_attack_locks_every_movement_direction_for_all_dt_partitions(self):
        partitions = ((0.6,), (0.05,) * 12, (0.016,) * 37 + (0.008,), (0.01,) * 60)
        for name, axis in (("forward", (1, -1)), ("backward", (-1, 1)),
                           ("side_right", (1, 1)), ("side_left", (-1, -1))):
            for steps in partitions:
                with self.subTest(direction=name, steps=len(steps)):
                    world, motion = self.make_world(), Locomotion()
                    self.advance(world, motion, 0.08, (1, 0))
                    self.assertAlmostEqual(motion.phase, 7.2 / 64)
                    origin = (world.player.x, world.player.y)
                    self.assertTrue(world.start_attack("front_right"))
                    distance = sum(self.advance(world, motion, dt, axis) for dt in steps)
                    self.assertEqual(distance, 0.0)
                    self.assertEqual((world.player.x, world.player.y), origin)
                    self.assertIsNone(world.attack)
                    self.assertEqual(motion.facing, "front_right")
                    self.assertAlmostEqual(motion.phase, 7.2 / 64)
                    self.assertEqual(motion.walk_frame_index(8), 0)
                    resumed_distance = 5.2 if name == "backward" else 7.2
                    self.assertAlmostEqual(self.advance(world, motion, 0.08, axis), resumed_distance)
                    self.assertAlmostEqual(motion.phase, (7.2 + resumed_distance) / 64)
                    self.assertEqual(motion.walk_frame_index(8), 2)

    def test_stop_and_resume_select_idle_without_losing_the_attack_walk_phase(self):
        world, motion = self.make_world(), Locomotion()
        self.advance(world, motion, 0.08, (1, 0))
        world.start_attack()
        self.advance(world, motion, 0.1, (1, -1))
        self.assertAlmostEqual(motion.phase, 7.2 / 64)
        self.assertEqual(motion.walk_frame_index(8), 0)
        self.assertEqual(self.advance(world, motion, 0.2), 0.0)
        self.assertAlmostEqual(world.attack.elapsed, 0.3)
        self.assertAlmostEqual(motion.phase, 7.2 / 64)
        self.assertEqual(motion.walk_frame_index(8), 0)
        self.advance(world, motion, 0.1, (1, -1))
        self.assertAlmostEqual(motion.phase, 7.2 / 64)
        self.assertEqual(motion.walk_frame_index(8), 0)
        self.advance(world, motion, 0.2, (1, -1))
        self.assertIsNone(world.attack)
        self.assertAlmostEqual(motion.phase, 7.2 / 64)
        self.assertEqual(motion.walk_frame_index(8), 0)

    def test_attack_near_wall_resumes_from_saved_phase(self):
        world, motion = self.make_world(), Locomotion()
        world.walls = [Wall(400, 330, 220, 60)]
        world.player.y = 310.0
        self.advance(world, motion, 0.08, (1, 0))
        world.start_attack()
        self.assertEqual(self.advance(world, motion, 0.1, (0, 1)), 0.0)
        self.assertEqual(world.player.y, 310.0)
        self.assertAlmostEqual(motion.phase, 7.2 / 64)
        self.assertAlmostEqual(self.advance(world, motion, 0.2, (0, 1)), 0.0)
        self.assertAlmostEqual(motion.phase, 7.2 / 64)
        self.assertEqual(motion.walk_frame_index(8), 0)
        self.assertAlmostEqual(world.attack.elapsed, 0.3)
        self.assertEqual(self.advance(world, motion, 0.1, (0, -1)), 0.0)
        self.advance(world, motion, 0.3, (0, 1))
        self.assertIsNone(world.attack)
        self.assertEqual(world.player.y, 316.0)
        self.assertAlmostEqual(motion.phase, (7.2 + 6.0) / 64)

    def test_zero_dt_focus_pause_freezes_combat_and_phase_then_resumes(self):
        world, motion = self.make_world(), Locomotion()
        self.advance(world, motion, 0.08, (1, 0))
        world.zombie.x = world.player.x + 60 / math.sqrt(2)
        world.zombie.y = world.player.y - 60 / math.sqrt(2)
        world.start_attack()
        self.advance(world, motion, 0.18, (-1, 1))
        self.assertEqual((world.player_hp, world.zombie.hp, world.zombie.stun_remaining), (3, 4, STUN_DURATION))
        before = (world.player.x, world.player.y, world.zombie.x, world.zombie.y,
                  world.attack.elapsed, world.player_hp, world.zombie.hp,
                  world.zombie.stun_remaining, world.player_invulnerable_remaining, motion.phase)
        for _ in range(3):
            self.assertEqual(self.advance(world, motion, 0.0, (1, -1)), 0.0)
            self.assertEqual((world.player.x, world.player.y, world.zombie.x, world.zombie.y,
                              world.attack.elapsed, world.player_hp, world.zombie.hp,
                              world.zombie.stun_remaining, world.player_invulnerable_remaining,
                              motion.phase), before)
            self.assertEqual(motion.walk_frame_index(8), 0)
        self.advance(world, motion, 0.1, (-1, 1))
        self.assertAlmostEqual(world.attack.elapsed, 0.28)
        self.assertAlmostEqual(world.zombie.stun_remaining, STUN_DURATION - 0.1)
        self.assertEqual(motion.phase, before[-1])
        self.assertFalse(motion.moving)

    def test_distance_driven_walking_preserves_hit_recovery_health_and_stun(self):
        for axis in ((0, 0), (-1, 1)):
            with self.subTest(axis=axis):
                world, motion = self.make_world(), Locomotion()
                world.zombie.x = world.player.x + 60 / math.sqrt(2)
                world.zombie.y = world.player.y - 60 / math.sqrt(2)
                world.start_attack()
                for dt, elapsed, hp, stun in ((0.179, 0.179, 5, 0.0),
                                               (0.001, 0.18, 4, STUN_DURATION),
                                               (0.1, 0.28, 4, STUN_DURATION - 0.1),
                                               (0.32, 0.6, 4, STUN_DURATION - 0.42)):
                    self.advance(world, motion, dt, axis)
                    self.assertEqual((world.player_hp, world.zombie.hp, world.result), (3, hp, "playing"))
                    self.assertAlmostEqual(world.zombie.stun_remaining, stun)
                    self.assertEqual(world.player_invulnerable_remaining, 0.0)
                    if elapsed < 0.6:
                        self.assertAlmostEqual(world.attack.elapsed, elapsed)
                        self.assertFalse(world.start_attack())
                    else:
                        self.assertIsNone(world.attack)
                self.assertEqual(motion.phase, 0.0)
                self.assertTrue(world.start_attack())

    def test_restart_recreates_locomotion_and_resets_world_after_zombie_strikes(self):
        world, motion = self.make_world(), Locomotion()
        self.advance(world, motion, 0.08, (1, 0))
        world.zombie.x, world.zombie.y = world.player.x + 28.0, world.player.y
        for dt in (0.3, 1.6, 1.6):
            self.advance(world, motion, dt)
        self.assertEqual((world.player_hp, world.result), (0, "defeated"))
        self.assertAlmostEqual(motion.phase, 0.1125)
        # R 입력의 공개 상태 초기화 계약이며 실제 SDL 입력 검사는 별도다.
        world.reset()
        motion = Locomotion()
        self.assertEqual((world.player.x, world.player.y), (480.0, 180.0))
        self.assertEqual((world.player_hp, world.zombie.hp, world.result), (3, 5, "playing"))
        self.assertEqual((world.zombie.stun_remaining, world.player_invulnerable_remaining), (0.0, 0.0))
        self.assertIsNone(world.attack)
        self.assertEqual((motion.phase, motion.moving, motion.walk_frame_index(8)), (0.0, False, 0))
        world.player.aim_angle = -math.pi / 4
        self.assertTrue(world.start_attack())
        self.assertEqual(self.advance(world, motion, 0.1, (1, 0)), 0.0)
        self.assertEqual(motion.phase, 0.0)
        self.assertEqual(motion.walk_frame_index(8), 0)


if __name__ == "__main__":
    unittest.main()
