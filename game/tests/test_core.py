"""R1-A public movement and ground-aim contract."""
import math
from pathlib import Path
import subprocess
import sys
import unittest

from game.core import Player, Wall, aim_player, move_player


class MovementTests(unittest.TestCase):
    def test_walks_90_ground_pixels_per_second_in_eight_directions(self):
        for axis in ((1, 0), (-1, 0), (0, 1), (0, -1),
                     (1, 1), (-1, 1), (1, -1), (-1, -1)):
            with self.subTest(axis=axis):
                player = Player()
                angle = player.aim_angle
                move_player(player, *axis, 1.0, ())
                self.assertAlmostEqual(math.dist((480.0, 180.0), (player.x, player.y)), 90.0)
                self.assertEqual(player.aim_angle, angle)
                self.assertTrue(player.moved)
                if axis[0] == 0:
                    self.assertEqual(player.x, 480.0)
                elif axis[1] == 0:
                    self.assertEqual(player.y, 180.0)
                else:
                    self.assertAlmostEqual(abs(player.x - 480.0), abs(player.y - 180.0))

    def test_all_wall_faces_stop_at_radius_then_allow_sliding_and_retreat(self):
        wall = Wall(400.0, 330.0, 220.0, 60.0)
        cases = (
            ((480.0, 300.0), (0, 1), (480.0, 316.0), (1, 1), "y"),
            ((480.0, 420.0), (0, -1), (480.0, 404.0), (1, -1), "y"),
            ((370.0, 360.0), (1, 0), (386.0, 360.0), (1, 1), "x"),
            ((650.0, 360.0), (-1, 0), (634.0, 360.0), (-1, 1), "x"),
        )
        for start, towards, contact, slide, blocked_axis in cases:
            with self.subTest(start=start):
                player = Player(*start)
                move_player(player, *towards, 1.0, (wall,))
                self.assertEqual((player.x, player.y), contact)
                self.assertTrue(player.moved)
                move_player(player, *towards, 0.05, (wall,))
                self.assertEqual((player.x, player.y), contact)
                self.assertFalse(player.moved)
                move_player(player, *slide, 0.1, (wall,))
                self.assertEqual(getattr(player, blocked_axis), getattr(Player(*contact), blocked_axis))
                self.assertNotEqual((player.x, player.y), contact)
                self.assertTrue(player.moved)
                before = (player.x, player.y)
                move_player(player, -towards[0], -towards[1], 0.05, (wall,))
                self.assertNotEqual((player.x, player.y), before)
                self.assertTrue(player.moved)

    def test_no_input_clears_moved_without_changing_pose(self):
        player = Player()
        move_player(player, 1, 0, 0.05, ())
        self.assertTrue(player.moved)
        pose = (player.x, player.y, player.aim_angle)
        move_player(player, 0, 0, 0.05, ())
        self.assertEqual((player.x, player.y, player.aim_angle), pose)
        self.assertFalse(player.moved)

    def test_frame_sized_updates_cover_90_pixels_in_one_second(self):
        player = Player()
        for _ in range(20):
            move_player(player, 1, 0, 0.05, ())
        self.assertAlmostEqual(player.x, 570.0)
        self.assertEqual(player.y, 180.0)

    def test_world_edges_keep_the_entire_radius_inside(self):
        cases = (
            ((1, 0), (946.0, 180.0)), ((-1, 0), (14.0, 180.0)),
            ((0, 1), (480.0, 706.0)), ((0, -1), (480.0, 14.0)),
            ((1, 1), (946.0, 706.0)), ((1, -1), (946.0, 14.0)),
            ((-1, 1), (14.0, 706.0)), ((-1, -1), (14.0, 14.0)),
        )
        for axis, endpoint in cases:
            with self.subTest(axis=axis):
                player = Player()
                move_player(player, *axis, 20.0, ())
                self.assertEqual((player.x, player.y), endpoint)
                self.assertTrue(player.moved)
                move_player(player, *axis, 0.05, ())
                self.assertEqual((player.x, player.y), endpoint)
                self.assertFalse(player.moved)

    def test_large_dt_cannot_cross_the_wall_from_any_side(self):
        wall = Wall(400.0, 330.0, 220.0, 60.0)
        cases = (
            ((480.0, 180.0), (0, 1), (480.0, 316.0)),
            ((480.0, 600.0), (0, -1), (480.0, 404.0)),
            ((100.0, 360.0), (1, 0), (386.0, 360.0)),
            ((900.0, 360.0), (-1, 0), (634.0, 360.0)),
        )
        for start, axis, endpoint in cases:
            with self.subTest(start=start):
                player = Player(*start)
                move_player(player, *axis, 8.0, (wall,))
                self.assertEqual((player.x, player.y), endpoint)

    def test_wall_tangent_paths_are_not_blocked(self):
        wall = Wall(400.0, 330.0, 220.0, 60.0)
        for start, axis, endpoint in (
            ((350.0, 316.0), (1, 0), (440.0, 316.0)),
            ((386.0, 290.0), (0, 1), (386.0, 380.0)),
        ):
            with self.subTest(start=start):
                player = Player(*start)
                move_player(player, *axis, 1.0, (wall,))
                self.assertAlmostEqual(player.x, endpoint[0])
                self.assertAlmostEqual(player.y, endpoint[1])
                self.assertTrue(player.moved)

    def test_circle_contacts_the_corner_without_box_shaped_padding(self):
        player = Player(380.0, 322.0)
        move_player(player, 1, 0, 0.2, (Wall(400.0, 330.0, 220.0, 60.0),))
        self.assertAlmostEqual(math.dist((player.x, player.y), (400.0, 330.0)), 14.0)
        self.assertGreater(player.x, 386.0)
        self.assertLess(player.x, 400.0)
        self.assertEqual(player.y, 322.0)

    def test_diagonal_corner_approaches_do_not_enter_the_wall(self):
        wall = Wall(400.0, 330.0, 220.0, 60.0)
        for start, axis in (
            ((360.0, 290.0), (1, 1)), ((660.0, 290.0), (-1, 1)),
            ((360.0, 430.0), (1, -1)), ((660.0, 430.0), (-1, -1)),
        ):
            with self.subTest(start=start):
                player = Player(*start)
                for _ in range(80):
                    move_player(player, *axis, 0.05, (wall,))
                    nearest = (max(400.0, min(620.0, player.x)),
                               max(330.0, min(390.0, player.y)))
                    self.assertGreaterEqual(math.dist((player.x, player.y), nearest), 14.0 - 1e-9)

    def test_invalid_dt_does_not_move_and_clears_moved(self):
        for dt in (0.0, -0.05, math.nan, math.inf, -math.inf, None, "0.05"):
            with self.subTest(dt=dt):
                player = Player(moved=True)
                move_player(player, 1, 0, dt, ())
                self.assertEqual((player.x, player.y, player.aim_angle), (480.0, 180.0, math.pi / 4))
                self.assertFalse(player.moved)

    def test_huge_finite_dt_stops_at_world_bounds_without_overflow(self):
        player = Player()
        move_player(player, 1, 1, 1e308, ())
        self.assertEqual((player.x, player.y), (946.0, 706.0))
        self.assertTrue(player.moved)

    def test_huge_dt_with_a_tiny_secondary_axis_finishes_promptly(self):
        # A subprocess watchdog keeps an accidental billion-tick loop bounded.
        code = (
            "from game.core import Player, move_player; "
            "p=Player(); move_player(p, 1, 1e-8, 1e308, ()); "
            "assert p.x == 946.0 and 180.0 < p.y < 181.0 and p.moved"
        )
        result = subprocess.run(
            [sys.executable, "-B", "-c", code],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True, text=True, timeout=3,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


class AimTests(unittest.TestCase):
    def test_aim_uses_counterclockwise_ground_radians(self):
        for offset, expected in (
            ((100, 0), 0.0), ((100, 100), math.pi / 4),
            ((0, 100), math.pi / 2), ((-100, 100), math.pi * 3 / 4),
            ((-100, 0), math.pi), ((-100, -100), -math.pi * 3 / 4),
            ((0, -100), -math.pi / 2), ((100, -100), -math.pi / 4),
        ):
            with self.subTest(offset=offset):
                player = Player()
                aim_player(player, player.x + offset[0], player.y + offset[1])
                self.assertAlmostEqual(player.aim_angle, expected)

    def test_aim_is_continuous_instead_of_quantized(self):
        player = Player()
        aim_player(player, 580.0, 205.0)
        self.assertAlmostEqual(player.aim_angle, 0.24497866312686414)

    def test_same_point_aim_preserves_angle_and_last_movement_flag(self):
        player = Player(aim_angle=1.2345, moved=True)
        aim_player(player, player.x, player.y)
        self.assertEqual(player.aim_angle, 1.2345)
        self.assertEqual((player.x, player.y), (480.0, 180.0))
        self.assertTrue(player.moved)

    def test_movement_and_aim_remain_independent(self):
        player = Player(200.0, 200.0)
        aim_player(player, 100.0, 200.0)
        move_player(player, 1, 0, 0.5, ())
        self.assertAlmostEqual(player.x, 245.0)
        self.assertEqual(player.y, 200.0)
        self.assertAlmostEqual(player.aim_angle, math.pi)
        before = (player.x, player.y, player.moved)
        aim_player(player, player.x, player.y + 100)
        self.assertEqual((player.x, player.y, player.moved), before)
        self.assertAlmostEqual(player.aim_angle, math.pi / 2)


if __name__ == "__main__":
    unittest.main()
