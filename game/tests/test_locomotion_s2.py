"""S2 integration checks for four aim facings with eight walk frames."""
import math
import unittest

from game.core import Player, Wall, move_player
from game.locomotion import Locomotion


class FourDirectionWalkTests(unittest.TestCase):
    def test_two_seconds_at_90_pixels_per_second_has_two_cycles_and_five_half_steps(self):
        for frames in (40, 120, 240):
            with self.subTest(frames=frames):
                player, pose = Player(240.0, 180.0), Locomotion()
                cycles = half_steps = 0
                for _ in range(frames):
                    before, phase = (player.x, player.y), pose.phase
                    move_player(player, 1, 0, 2.0 / frames, ())
                    pose.update(-math.pi / 4, player.x - before[0], player.y - before[1])
                    cycles += pose.phase < phase
                    half_steps += (pose.phase < 0.5) != (phase < 0.5)
                self.assertAlmostEqual(player.x - 240.0, 180.0)
                self.assertEqual(player.y, 180.0)
                self.assertEqual((cycles, half_steps), (2, 5))
                self.assertAlmostEqual(pose.phase, 0.8125, places=11)
                self.assertEqual(pose.walk_frame_index(8), 7)

    def test_actual_forward_backward_and_sideways_distance_in_all_facings(self):
        cases = (
            ("front_right", -math.pi / 4, ((1, -1), (-1, 1), (1, 1))),
            ("back_right", math.pi / 4, ((1, 1), (-1, -1), (-1, 1))),
            ("back_left", 3 * math.pi / 4, ((-1, 1), (1, -1), (-1, -1))),
            ("front_left", -3 * math.pi / 4, ((-1, -1), (1, 1), (1, -1))),
        )
        for facing, angle, axes in cases:
            for axis in axes:
                for frames in (8, 24, 60):
                    with self.subTest(facing=facing, axis=axis, frames=frames):
                        player = Player(240.0, 180.0, aim_angle=angle)
                        pose = Locomotion()
                        for _ in range(frames):
                            before = (player.x, player.y)
                            move_player(player, *axis, 0.4 / frames, (Wall(400, 330, 220, 60),))
                            pose.update(player.aim_angle, player.x - before[0], player.y - before[1])
                        self.assertAlmostEqual(math.dist((240.0, 180.0), (player.x, player.y)), 36.0)
                        self.assertEqual(player.aim_angle, angle)
                        self.assertEqual(pose.facing, facing)
                        self.assertAlmostEqual(pose.phase, 0.5625, places=11)
                        self.assertTrue(pose.moving)
                        self.assertEqual(pose.walk_frame_index(8), 5)

    def test_turn_stop_and_resume_preserve_phase_through_all_four_facings(self):
        pose = Locomotion()
        pose.update(-math.pi / 4, 18, 0)
        self.assertEqual((pose.phase, pose.walk_frame_index(8)), (0.28125, 3))
        for facing, angle, next_phase, frame in (
            ("back_right", math.pi / 4, 0.3125, 3),
            ("back_left", 3 * math.pi / 4, 0.34375, 3),
            ("front_left", -3 * math.pi / 4, 0.375, 4),
            ("front_right", -math.pi / 4, 0.40625, 4),
        ):
            with self.subTest(facing=facing):
                phase = pose.phase
                pose.update(angle, 0, 0)
                self.assertEqual((pose.facing, pose.phase, pose.moving), (facing, phase, False))
                self.assertEqual(pose.walk_frame_index(8), 0)
                pose.update(angle, -2, 0)
                self.assertEqual((pose.facing, pose.phase, pose.walk_frame_index(8)),
                                 (facing, next_phase, frame))

    def test_wall_stop_and_retreat_use_actual_displacement_in_each_facing(self):
        cases = (
            ("front_right", -math.pi / 4, (480.0, 300.0), (0, 1), (480.0, 316.0)),
            ("back_right", math.pi / 4, (480.0, 420.0), (0, -1), (480.0, 404.0)),
            ("back_left", 3 * math.pi / 4, (370.0, 360.0), (1, 0), (386.0, 360.0)),
            ("front_left", -3 * math.pi / 4, (650.0, 360.0), (-1, 0), (634.0, 360.0)),
        )
        for facing, angle, start, axis, contact in cases:
            with self.subTest(facing=facing):
                player = Player(*start, aim_angle=angle)
                pose = Locomotion()
                walls = (Wall(400, 330, 220, 60),)
                for _ in range(4):
                    before = (player.x, player.y)
                    move_player(player, *axis, 0.05, walls)
                    pose.update(player.aim_angle, player.x - before[0], player.y - before[1])
                self.assertEqual((player.x, player.y), contact)
                self.assertEqual((pose.phase, pose.walk_frame_index(8)), (0.25, 3))
                for _ in range(3):
                    move_player(player, *axis, 0.05, walls)
                    pose.update(player.aim_angle, player.x - contact[0], player.y - contact[1])
                    self.assertFalse(player.moved)
                    self.assertEqual((pose.facing, pose.phase, pose.moving), (facing, 0.25, False))
                    self.assertEqual(pose.walk_frame_index(8), 0)
                move_player(player, -axis[0], -axis[1], 0.05, walls)
                pose.update(player.aim_angle, player.x - contact[0], player.y - contact[1])
                self.assertEqual((pose.facing, pose.phase, pose.walk_frame_index(8)), (facing, 0.3203125, 3))

    def test_sliding_uses_tangent_distance_instead_of_requested_speed(self):
        cases = (
            ("front_right", -math.pi / 4, (480.0, 316.0), (1, 1)),
            ("back_right", math.pi / 4, (480.0, 404.0), (1, -1)),
            ("back_left", 3 * math.pi / 4, (386.0, 360.0), (1, 1)),
            ("front_left", -3 * math.pi / 4, (634.0, 360.0), (-1, 1)),
        )
        for facing, angle, start, axis in cases:
            with self.subTest(facing=facing):
                player = Player(*start, aim_angle=angle)
                move_player(player, *axis, 0.05, (Wall(400, 330, 220, 60),))
                dx, dy = player.x - start[0], player.y - start[1]
                self.assertAlmostEqual(math.hypot(dx, dy), 3.181980515339464)
                pose = Locomotion()
                # Keep a frame boundary between actual sliding and a requested 4.5px step.
                pose.update(player.aim_angle, 4, 0)
                pose.update(player.aim_angle, dx, dy)
                self.assertEqual(pose.facing, facing)
                self.assertAlmostEqual(pose.phase, 0.11221844555217912)
                self.assertTrue(pose.moving)
                self.assertEqual(pose.walk_frame_index(8), 1)

    def test_facing_boundary_cycle_wrap_and_idle_return_in_all_directions(self):
        for facing, center, next_facing in (
            ("front_right", -45, "back_right"),
            ("back_right", 45, "back_left"),
            ("back_left", 135, "front_left"),
            ("front_left", -135, "front_right"),
        ):
            with self.subTest(facing=facing):
                pose = Locomotion()
                pose.update(math.radians(center), 56, 0)
                self.assertEqual((pose.facing, pose.phase, pose.walk_frame_index(8)), (facing, 0.875, 8))
                pose.update(math.radians(center + 50), 0, 0)
                self.assertEqual((pose.facing, pose.phase, pose.walk_frame_index(8)), (facing, 0.875, 0))
                pose.update(math.radians(center + 50.001), 8, 0)
                self.assertEqual((pose.facing, pose.phase, pose.walk_frame_index(8)), (next_facing, 0.0, 1))
                pose.update(math.radians(center + 50.001), 0, 0)
                self.assertEqual((pose.phase, pose.walk_frame_index(8)), (0.0, 0))
                pose.update(math.radians(center + 50.001), -8, 0)
                self.assertEqual((pose.facing, pose.phase, pose.walk_frame_index(8)), (next_facing, 0.125, 2))


if __name__ == "__main__":
    unittest.main()
