"""R1-B direction selection and distance-based pose contract."""
import math
import unittest

from game.core import Player, Wall, move_player
from game.locomotion import Locomotion, select_facing


class FacingTests(unittest.TestCase):
    def test_initial_selection_uses_the_nearest_representative(self):
        for degrees, expected in (
            (-45, "front_right"), (45, "back_right"),
            (135, "back_left"), (-135, "front_left"),
            (2, "back_right"), (-2, "front_right"),
            (88, "back_right"), (92, "back_left"),
            (-88, "front_right"), (-92, "front_left"),
        ):
            with self.subTest(degrees=degrees):
                self.assertEqual(select_facing(math.radians(degrees)), expected)

    def test_ties_use_contract_order_including_near_equal_float_distances(self):
        for angle, expected in (
            (0.0, "front_right"), (math.pi / 2, "back_right"),
            (math.pi, "back_left"), (-math.pi, "back_left"),
            (-math.pi / 2, "front_right"),
            (2.5e-13, "front_right"), (2e-12, "back_right"),
            (math.pi + 2.5e-13, "back_left"), (math.pi + 2e-12, "front_left"),
        ):
            with self.subTest(angle=angle):
                self.assertEqual(select_facing(angle), expected)

    def test_hysteresis_keeps_each_direction_through_50_degrees(self):
        for current, center, forward, backward in (
            ("front_right", -45, "back_right", "front_left"),
            ("back_right", 45, "back_left", "front_right"),
            ("back_left", 135, "front_left", "back_right"),
            ("front_left", -135, "front_right", "back_left"),
        ):
            for offset, expected in (
                (49.9, current), (50.0, current), (50.001, forward),
                (-49.9, current), (-50.0, current), (-50.001, backward),
            ):
                with self.subTest(current=current, offset=offset):
                    self.assertEqual(select_facing(math.radians(center + offset), current), expected)

    def test_equivalent_angles_wrap_consistently(self):
        for angle, expected in (
            (0.0, "front_right"), (math.pi / 2, "back_right"),
            (math.pi, "back_left"), (-math.pi / 2, "front_right"),
            (math.radians(179), "back_left"), (math.radians(-179), "front_left"),
        ):
            for turns in (-3, -1, 0, 1, 3):
                with self.subTest(angle=angle, turns=turns):
                    self.assertEqual(select_facing(angle + math.tau * turns), expected)
        self.assertEqual(select_facing(math.radians(-179), "back_left"), "back_left")
        self.assertEqual(select_facing(math.radians(179), "front_left"), "front_left")

    def test_invalid_angle_preserves_a_valid_current_or_uses_the_default(self):
        for angle in (math.nan, math.inf, -math.inf, None, "0.0", 1j):
            with self.subTest(angle=angle):
                self.assertEqual(select_facing(angle, "back_left"), "back_left")
                self.assertEqual(select_facing(angle), "front_right")
        self.assertEqual(select_facing(math.pi / 4, "unknown"), "back_right")


class LocomotionTests(unittest.TestCase):
    def test_frames_follow_the_32_pixel_walking_cycle(self):
        pose = Locomotion()
        self.assertEqual((pose.facing, pose.phase, pose.moving, pose.frame_index),
                         ("front_right", 0.0, False, 0))
        for distance, phase, frame in ((8, 0.25, 1), (8, 0.5, 2), (16, 0.0, 1)):
            pose.update(-math.pi / 4, distance, 0)
            self.assertEqual(pose.phase, phase)
            self.assertTrue(pose.moving)
            self.assertEqual(pose.frame_index, frame)
        pose.update(-math.pi / 4, 0, 0)
        self.assertEqual(pose.phase, 0.0)
        self.assertFalse(pose.moving)
        self.assertEqual(pose.frame_index, 0)

    def test_first_valid_update_does_not_apply_default_facing_hysteresis(self):
        pose = Locomotion()
        pose.update(math.radians(2), 0, 0)
        self.assertEqual(pose.facing, "back_right")
        pose.update(math.radians(-2), 0, 0)
        self.assertEqual(pose.facing, "back_right")

    def test_distance_partition_is_frame_rate_independent(self):
        for distance, phase, frame in ((32.0, 0.0, 1), (48.0, 0.5, 2), (40.0, 0.25, 1)):
            for frames in (1, 10, 30, 60, 100, 144):
                with self.subTest(distance=distance, frames=frames):
                    pose = Locomotion()
                    for _ in range(frames):
                        pose.update(-math.pi / 4, distance / frames, 0)
                    self.assertAlmostEqual(pose.phase, phase)
                    self.assertEqual(pose.frame_index, frame)

    def test_displacement_uses_euclidean_distance(self):
        pose = Locomotion()
        pose.update(math.pi / 4, 3, 4)
        self.assertEqual(pose.phase, 0.15625)
        self.assertTrue(pose.moving)

    def test_backward_and_sideways_displacement_does_not_change_aim_facing(self):
        for dx, dy in ((8, 0), (-8, 0), (0, 8), (0, -8)):
            with self.subTest(displacement=(dx, dy)):
                pose = Locomotion()
                pose.update(math.pi / 4, dx, dy)
                self.assertEqual(pose.facing, "back_right")
                self.assertEqual(pose.phase, 0.25)
                self.assertEqual(pose.frame_index, 1)

    def test_stopping_and_turning_preserve_the_existing_phase(self):
        pose = Locomotion()
        pose.update(-math.pi / 4, 8, 0)
        for _ in range(5):
            pose.update(-math.pi / 4, 0, 0)
            self.assertEqual((pose.phase, pose.frame_index), (0.25, 0))
        pose.update(3 * math.pi / 4, 0, 0)
        self.assertEqual((pose.facing, pose.phase, pose.frame_index), ("back_left", 0.25, 0))
        pose.update(-3 * math.pi / 4, 4, 0)
        self.assertEqual((pose.facing, pose.phase, pose.frame_index), ("front_left", 0.375, 1))

    def test_actual_wall_blocked_displacement_produces_idle_without_resetting_phase(self):
        player = Player(480.0, 316.0)
        pose = Locomotion()
        pose.update(math.pi / 4, 8, 0)
        before = (player.x, player.y)
        move_player(player, 0, 1, 0.05, (Wall(400, 330, 220, 60),))
        self.assertEqual((player.x, player.y), before)
        pose.update(player.aim_angle, player.x - before[0], player.y - before[1])
        self.assertEqual(pose.phase, 0.25)
        self.assertFalse(pose.moving)
        self.assertEqual(pose.frame_index, 0)

    def test_displacement_at_or_below_epsilon_is_idle(self):
        pose = Locomotion()
        pose.update(-math.pi / 4, 8, 0)
        for dx, dy in ((0, 0), (1e-7, 0), (1e-6, 0), (0.6e-6, 0.8e-6)):
            with self.subTest(displacement=(dx, dy)):
                pose.update(-math.pi / 4, dx, dy)
                self.assertEqual((pose.phase, pose.moving, pose.frame_index), (0.25, False, 0))
        pose.update(-math.pi / 4, 1.001e-6, 0)
        self.assertTrue(pose.moving)
        self.assertGreater(pose.phase, 0.25)

    def test_invalid_input_preserves_pose_and_does_not_consume_initial_selection(self):
        for values in (
            (math.nan, 8, 0), (math.inf, 8, 0), (-math.inf, 0, 0),
            (None, 0, 0), ("0.0", 0, 0),
            (math.pi / 4, math.nan, 0), (math.pi / 4, 0, math.inf),
            (math.pi / 4, None, 0), (math.pi / 4, 1j, 0),
            (math.pi / 4, 1.7e308, 1.7e308),
        ):
            with self.subTest(values=values):
                pose = Locomotion()
                pose.update(*values)
                self.assertEqual((pose.facing, pose.phase, pose.moving, pose.frame_index),
                                 ("front_right", 0.0, False, 0))
                pose.update(math.radians(2), 0, 0)
                self.assertEqual(pose.facing, "back_right")
                pose.update(-math.pi / 4, 8, 0)
                before = (pose.facing, pose.phase)
                pose.update(*values)
                self.assertEqual((pose.facing, pose.phase), before)
                self.assertEqual((pose.moving, pose.frame_index), (False, 0))

    def test_large_finite_distance_keeps_fractional_phase(self):
        pose = Locomotion()
        pose.update(-math.pi / 4, 8, 0)
        pose.update(math.pi / 4, 1e308, 0)
        self.assertEqual((pose.facing, pose.phase, pose.frame_index), ("back_right", 0.25, 1))


class WalkFrameIndexTests(unittest.TestCase):
    def test_idle_and_two_eight_frame_selection(self):
        pose = Locomotion(phase=0.25)
        self.assertEqual(pose.walk_frame_index(2), 0)
        self.assertEqual(pose.walk_frame_index(8), 0)
        pose.moving = True
        self.assertEqual(pose.walk_frame_index(2), 1)
        self.assertEqual(pose.walk_frame_index(8), 3)

    def test_exact_boundaries_and_adjacent_intervals(self):
        for count in (2, 8):
            for index in range(count):
                boundary = index / count
                with self.subTest(count=count, boundary=boundary):
                    pose = Locomotion(phase=boundary, moving=True)
                    self.assertEqual(pose.walk_frame_index(count), index + 1)
                    if index:
                        pose.phase = boundary - 1e-8
                        self.assertEqual(pose.walk_frame_index(count), index)
                    pose.phase = boundary + 1e-8
                    self.assertEqual(pose.walk_frame_index(count), index + 1)
            pose = Locomotion(phase=1.0 - 1e-13, moving=True)
            self.assertEqual(pose.walk_frame_index(count), count)

    def test_two_frames_match_the_legacy_property(self):
        for moving in (False, True):
            for phase in (0.0, 0.125, 0.5 - 1e-13, 0.5, 0.5 + 1e-13, 0.875, 1.0 - 1e-13):
                with self.subTest(moving=moving, phase=phase):
                    pose = Locomotion(phase=phase, moving=moving)
                    self.assertEqual(pose.walk_frame_index(2), pose.frame_index)

    def test_invalid_count_raises_even_when_idle_and_keeps_state(self):
        for moving in (False, True):
            for count in (0, -1, True, False, 2.0, 8.0, None, "8", math.nan, math.inf):
                with self.subTest(moving=moving, count=count):
                    pose = Locomotion(facing="back_left", phase=0.25, moving=moving)
                    with self.assertRaises(ValueError):
                        pose.walk_frame_index(count)
                    self.assertEqual((pose.facing, pose.phase, pose.moving), ("back_left", 0.25, moving))

    def test_queries_keep_phase_facing_moving_and_initial_selection(self):
        pose = Locomotion(phase=0.3125, moving=True)
        before = (pose.facing, pose.phase, pose.moving, pose.frame_index)
        for count in (2, 8, 8, 2, 1, 3):
            pose.walk_frame_index(count)
            self.assertEqual((pose.facing, pose.phase, pose.moving, pose.frame_index), before)
        pose.update(math.radians(2), 0, 0)
        self.assertEqual((pose.facing, pose.phase, pose.moving), ("back_right", 0.3125, False))
        self.assertEqual(pose.walk_frame_index(8), 0)

    def test_eight_frame_distance_partition_is_fps_independent(self):
        for distance, expected in ((4, 2), (8, 3), (12, 4), (16, 5), (20, 6),
                                   (24, 7), (28, 8), (32, 1), (36, 2), (48, 5)):
            for frames in (1, 10, 30, 60, 100, 144):
                with self.subTest(distance=distance, frames=frames):
                    pose = Locomotion()
                    for _ in range(frames):
                        pose.update(-math.pi / 4, distance / frames, 0)
                    before = (pose.facing, pose.phase, pose.moving)
                    self.assertEqual(pose.walk_frame_index(8), expected)
                    self.assertEqual((pose.facing, pose.phase, pose.moving), before)


if __name__ == "__main__":
    unittest.main()
