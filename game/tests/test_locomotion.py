"""R1-B direction selection and distance-based pose contract."""
import math
import unittest

from game.core import Player, Wall, move_player
from game.locomotion import Locomotion, select_facing


class FacingTests(unittest.TestCase):
    def test_initial_selection_uses_all_eight_representatives(self):
        for degrees, expected in (
            (0, "right"), (45, "back_right"), (90, "back"),
            (135, "back_left"), (180, "left"), (-135, "front_left"),
            (-90, "front"), (-45, "front_right"),
            (2, "right"), (-2, "right"), (88, "back"), (92, "back"),
            (-88, "front"), (-92, "front"),
        ):
            with self.subTest(degrees=degrees):
                self.assertEqual(select_facing(math.radians(degrees)), expected)

    def test_ties_use_contract_order_including_near_equal_float_distances(self):
        boundary = math.pi / 8
        for angle, expected in (
            (boundary, "right"), (3 * boundary, "back_right"),
            (5 * boundary, "back"), (7 * boundary, "back_left"),
            (-7 * boundary, "left"), (-5 * boundary, "front_left"),
            (-3 * boundary, "front"), (-boundary, "right"),
            (boundary + 2.5e-13, "right"), (boundary + 2e-12, "back_right"),
            (-7 * boundary + 2.5e-13, "left"),
            (-7 * boundary + 2e-12, "front_left"),
        ):
            with self.subTest(angle=angle):
                self.assertEqual(select_facing(angle), expected)

    def test_hysteresis_keeps_each_direction_through_27_5_degrees(self):
        for current, center, forward, backward in (
            ("right", 0, "back_right", "front_right"),
            ("back_right", 45, "back", "right"),
            ("back", 90, "back_left", "back_right"),
            ("back_left", 135, "left", "back"),
            ("left", 180, "front_left", "back_left"),
            ("front_left", -135, "front", "left"),
            ("front", -90, "front_right", "front_left"),
            ("front_right", -45, "right", "front"),
        ):
            for offset, expected in (
                (22.6, current), (27.5, current), (27.501, forward),
                (-22.6, current), (-27.5, current), (-27.501, backward),
            ):
                with self.subTest(current=current, offset=offset):
                    self.assertEqual(select_facing(math.radians(center + offset), current), expected)

    def test_equivalent_angles_wrap_consistently(self):
        for angle, expected in (
            (0.0, "right"), (math.pi / 4, "back_right"),
            (math.pi / 2, "back"), (3 * math.pi / 4, "back_left"),
            (math.pi, "left"), (-3 * math.pi / 4, "front_left"),
            (-math.pi / 2, "front"), (-math.pi / 4, "front_right"),
            (math.radians(179), "left"), (math.radians(-179), "left"),
        ):
            for turns in (-3, -1, 0, 1, 3):
                with self.subTest(angle=angle, turns=turns):
                    self.assertEqual(select_facing(angle + math.tau * turns), expected)
        self.assertEqual(select_facing(math.radians(-179), "left"), "left")
        self.assertEqual(select_facing(math.radians(179), "left"), "left")

    def test_invalid_angle_preserves_a_valid_current_or_uses_the_default(self):
        for angle in (math.nan, math.inf, -math.inf, None, "0.0", 1j):
            for current in ("right", "back_right", "back", "back_left",
                            "left", "front_left", "front", "front_right"):
                with self.subTest(angle=angle, current=current):
                    self.assertEqual(select_facing(angle, current), current)
            self.assertEqual(select_facing(angle), "front_right")
        self.assertEqual(select_facing(math.pi / 4, "unknown"), "back_right")



class LocomotionTests(unittest.TestCase):
    def test_frames_follow_the_64_pixel_walking_cycle(self):
        pose = Locomotion()
        self.assertEqual((pose.facing, pose.phase, pose.moving, pose.frame_index),
                         ("front_right", 0.0, False, 0))
        for distance, phase, frame in ((16, 0.25, 1), (16, 0.5, 2), (32, 0.0, 1)):
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
        pose.update(math.radians(-20), 0, 0)
        self.assertEqual(pose.facing, "right")
        pose.update(math.radians(-25), 0, 0)
        self.assertEqual(pose.facing, "right")

    def test_distance_partition_is_frame_rate_independent(self):
        for distance, phase, frame in ((64.0, 0.0, 1), (96.0, 0.5, 2), (80.0, 0.25, 1)):
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
        self.assertEqual(pose.phase, 0.078125)
        self.assertTrue(pose.moving)

    def test_backward_and_sideways_displacement_does_not_change_aim_facing(self):
        for dx, dy in ((16, 0), (-16, 0), (0, 16), (0, -16)):
            with self.subTest(displacement=(dx, dy)):
                pose = Locomotion()
                pose.update(math.pi / 4, dx, dy)
                self.assertEqual(pose.facing, "back_right")
                self.assertEqual(pose.phase, 0.25)
                self.assertEqual(pose.frame_index, 1)

    def test_stopping_and_turning_preserve_the_existing_phase(self):
        pose = Locomotion()
        pose.update(-math.pi / 4, 16, 0)
        for _ in range(5):
            pose.update(-math.pi / 4, 0, 0)
            self.assertEqual((pose.phase, pose.frame_index), (0.25, 0))
        pose.update(3 * math.pi / 4, 0, 0)
        self.assertEqual((pose.facing, pose.phase, pose.frame_index), ("back_left", 0.25, 0))
        pose.update(-3 * math.pi / 4, 8, 0)
        self.assertEqual((pose.facing, pose.phase, pose.frame_index), ("front_left", 0.375, 1))

    def test_actual_wall_blocked_displacement_produces_idle_without_resetting_phase(self):
        player = Player(480.0, 316.0)
        pose = Locomotion()
        pose.update(math.pi / 4, 16, 0)
        before = (player.x, player.y)
        move_player(player, 0, 1, 0.05, (Wall(400, 330, 220, 60),))
        self.assertEqual((player.x, player.y), before)
        pose.update(player.aim_angle, player.x - before[0], player.y - before[1])
        self.assertEqual(pose.phase, 0.25)
        self.assertFalse(pose.moving)
        self.assertEqual(pose.frame_index, 0)

    def test_displacement_at_or_below_epsilon_is_idle(self):
        pose = Locomotion()
        pose.update(-math.pi / 4, 16, 0)
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
                pose.update(math.radians(-20), 0, 0)
                self.assertEqual(pose.facing, "right")
                pose.update(-math.pi / 4, 8, 0)
                before = (pose.facing, pose.phase)
                pose.update(*values)
                self.assertEqual((pose.facing, pose.phase), before)
                self.assertEqual((pose.moving, pose.frame_index), (False, 0))

    def test_large_finite_distance_keeps_fractional_phase(self):
        pose = Locomotion()
        pose.update(-math.pi / 4, 16, 0)
        pose.update(math.pi / 4, 1e308, 0)
        self.assertEqual((pose.facing, pose.phase, pose.frame_index), ("back_right", 0.25, 1))

    def test_opt_in_backstep_plays_eight_frames_in_reverse_and_wraps(self):
        pose = Locomotion()
        frames = []
        for _ in range(8):
            pose.update(0, -8, 0, reverse_backstep=True)
            frames.append(pose.walk_frame_index(8))
        self.assertEqual(frames, [8, 7, 6, 5, 4, 3, 2, 1])
        self.assertEqual((pose.facing, pose.phase), ("right", 0))

    def test_opt_in_front_back_switches_and_turning_at_rest_keep_phase(self):
        pose = Locomotion()
        pose.update(0, 16, 0, reverse_backstep=True)
        self.assertEqual(pose.phase, .25)
        pose.update(0, -8, 0, reverse_backstep=True)
        self.assertEqual(pose.phase, .125)
        pose.update(math.pi, 0, 0, reverse_backstep=True)
        self.assertEqual((pose.facing, pose.phase, pose.walk_frame_index(8)), ("left", .125, 0))
        pose.update(math.pi, -8, 0, reverse_backstep=True)
        self.assertEqual(pose.phase, .25)
        pose.update(math.pi, 8, 0, reverse_backstep=True)
        self.assertEqual(pose.phase, .125)

    def test_opt_in_forward_sideways_and_backward_for_all_eight_facings(self):
        for facing, degrees in (("right", 0), ("back_right", 45), ("back", 90), ("back_left", 135),
                                ("left", 180), ("front_left", -135), ("front", -90), ("front_right", -45)):
            for offset, expected in ((0, .25), (90, .25), (-90, .25), (180, .75)):
                with self.subTest(facing=facing, movement_offset=offset):
                    move_angle = math.radians(degrees + offset)
                    pose = Locomotion()
                    pose.update(math.radians(degrees), 16 * math.cos(move_angle), 16 * math.sin(move_angle),
                                reverse_backstep=True)
                    self.assertEqual(pose.facing, facing)
                    self.assertAlmostEqual(pose.phase, expected)

    def test_opt_in_uses_the_facing_selected_with_hysteresis(self):
        pose = Locomotion()
        pose.update(0, 0, 0, reverse_backstep=True)
        pose.update(math.radians(25), 0, -8, reverse_backstep=True)
        self.assertEqual((pose.facing, pose.phase), ("right", .125))
        pose.update(math.radians(28), 0, -8, reverse_backstep=True)
        self.assertEqual((pose.facing, pose.phase), ("back_right", 0))

    def test_opt_in_large_and_invalid_displacements_preserve_existing_phase(self):
        pose = Locomotion(phase=.25)
        pose.update(math.pi / 4, -1.2e308, -1.2e308, reverse_backstep=True)
        self.assertEqual((pose.facing, pose.phase, pose.moving), ("back_right", .25, True))
        for dx, dy in ((math.nan, 0), (-1.7e308, -1.7e308)):
            with self.subTest(dx=dx, dy=dy):
                pose.update(0, dx, dy, reverse_backstep=True)
                self.assertEqual((pose.facing, pose.phase, pose.moving), ("back_right", .25, False))


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
        pose.update(math.radians(-20), 0, 0)
        self.assertEqual((pose.facing, pose.phase, pose.moving), ("right", 0.3125, False))
        self.assertEqual(pose.walk_frame_index(8), 0)

    def test_eight_frame_distance_partition_is_fps_independent(self):
        for distance, expected in ((8, 2), (16, 3), (24, 4), (32, 5), (40, 6),
                                   (48, 7), (56, 8), (64, 1), (72, 2), (96, 5)):
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
