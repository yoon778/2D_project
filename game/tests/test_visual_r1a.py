"""R1-A ground projection, mouse conversion, and painter-order contracts."""
from dataclasses import asdict
import json
import math
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import Player, Wall
from main import CAMERA_TIME, Renderer, screen_to_world, sdl_to_world, sorted_drawables, world_to_screen
from player_visual import METADATA_PATH, sprite_rect


class ProjectionTests(unittest.TestCase):
    def assertPointAlmostEqual(self, actual, expected):
        self.assertEqual(len(actual), 2)
        self.assertAlmostEqual(actual[0], expected[0], places=9)
        self.assertAlmostEqual(actual[1], expected[1], places=9)

    def test_ground_corners_have_expected_screen_positions(self):
        cases = (
            ((0.0, 0.0), (160.0, 90.0)),
            ((960.0, 0.0), (1120.0, 90.0)),
            ((0.0, 720.0), (160.0, 522.0)),
            ((960.0, 720.0), (1120.0, 522.0)),
        )
        for world, screen in cases:
            with self.subTest(world=world):
                self.assertPointAlmostEqual(world_to_screen(*world), screen)
                self.assertPointAlmostEqual(screen_to_world(*screen), world)

    def test_projection_round_trips_fractional_and_boundary_points(self):
        points = (
            (0.0, 0.0), (960.0, 720.0), (480.0, 180.0),
            (1.25, 719.5), (831.125, 263.875), (959.75, 0.125),
        )
        for world in points:
            with self.subTest(world=world):
                self.assertPointAlmostEqual(
                    screen_to_world(*world_to_screen(*world)), world,
                )
        for screen in ((0.0, 0.0), (1279.0, 719.0), (321.5, 111.25)):
            with self.subTest(screen=screen):
                self.assertPointAlmostEqual(
                    world_to_screen(*screen_to_world(*screen)), screen,
                )

    def test_sdl_mouse_uses_last_pixel_y_and_inverse_projection(self):
        cases = (
            ((0.0, 0.0), (-160.0, 1048.3333333333333)),
            ((1279.0, 719.0), (1119.0, -150.0)),
            ((640.0, 521.0), (480.0, 180.0)),
            ((321.5, 111.25), (161.5, 862.9166666666666)),
        )
        for mouse, world in cases:
            with self.subTest(mouse=mouse):
                self.assertPointAlmostEqual(sdl_to_world(*mouse), world)


class CameraTests(unittest.TestCase):
    def setUp(self):
        self.renderer = Renderer.__new__(Renderer)
        self.renderer.camera = (0, 0)
        self.renderer.delivery = SimpleNamespace(world_size=(3600, 2400))
        self.player = Player(1300, 900)

    def test_reset_restores_anchor_and_practice_keeps_fixed_camera(self):
        self.renderer.follow(self.player)
        self.assertEqual(world_to_screen(1300, 900, self.renderer.camera), (640, 306))
        self.renderer.delivery = None
        self.renderer.camera = (0, 0)
        self.renderer.follow(self.player, CAMERA_TIME, cursor=(1279, 0))
        self.assertEqual(self.renderer.camera, (0, 0))

    def test_diagonal_lead_is_capped_in_screen_pixels_and_is_frame_independent(self):
        self.renderer.follow(self.player)
        base = self.renderer.camera
        cursor = (1200, 65)
        self.renderer.follow(self.player, CAMERA_TIME, cursor=cursor)
        whole = self.renderer.camera
        lead = math.hypot(whole[0] - base[0], .6 * (whole[1] - base[1]))
        self.assertAlmostEqual(lead, 72 * (1 - math.exp(-1)))
        self.renderer.follow(self.player)
        for _ in range(10):
            self.renderer.follow(self.player, CAMERA_TIME / 10, cursor=cursor)
        for actual, expected in zip(self.renderer.camera, whole):
            self.assertAlmostEqual(actual, expected)

    def test_follow_clamps_to_old_map_edges_and_removes_lead_without_mouse(self):
        self.player.x, self.player.y = 3580, 2380
        self.renderer.follow(self.player)
        self.renderer.follow(self.player, 3, cursor=(1279, 0))
        self.assertEqual(self.renderer.camera, (2640, 1680))
        self.player.x, self.player.y = 20, 20
        self.renderer.follow(self.player)
        self.renderer.follow(self.player, 3, cursor=(0, 719))
        self.assertEqual(self.renderer.camera, (0, 0))
        self.player.x, self.player.y = 1300, 900
        self.renderer.follow(self.player)
        base = self.renderer.camera
        self.renderer.follow(self.player, 3, cursor=(1279, 413))
        self.assertGreater(self.renderer.camera[0], base[0] + 70)
        self.renderer.follow(self.player, 3)
        self.assertAlmostEqual(self.renderer.camera[0], base[0], places=6)
        self.assertAlmostEqual(self.renderer.camera[1], base[1])


class MapProjectionTests(unittest.TestCase):
    def test_sdl_mouse_maps_inside_actual_map_area_only(self):
        renderer = Renderer.__new__(Renderer)
        renderer.delivery = SimpleNamespace(world_size=(3600, 2400))
        for screen, world in (((64, 615), (0, 0)), ((856, 87), (3600, 2400)), ((460, 351), (1800, 1200))):
            with self.subTest(screen=screen):
                actual = renderer.map_world_at(*screen)
                self.assertAlmostEqual(actual[0], world[0])
                self.assertAlmostEqual(actual[1], world[1])
        for screen in ((63, 400), (857, 400), (400, 86), (400, 616), (1000, 350)):
            self.assertIsNone(renderer.map_world_at(*screen))


class DepthOrderTests(unittest.TestCase):
    def test_prop_uses_ground_depth_and_precedes_characters_on_ties(self):
        prop = (365.0, 300.0)
        for player_y, zombie_y, kinds in (
            (301.0, 299.0, ["player", "prop", "zombie"]),
            (299.0, 301.0, ["zombie", "prop", "player"]),
            (300.0, 300.0, ["prop", "zombie", "player"]),
        ):
            with self.subTest(player_y=player_y, zombie_y=zombie_y):
                drawn = sorted_drawables(Player(y=player_y), [], Player(y=zombie_y), prop=prop)
                self.assertEqual([kind for kind, _ in drawn], kinds)

    def test_player_behind_in_front_and_on_wall_baseline(self):
        wall = Wall(400.0, 330.0, 220.0, 60.0)
        for player_y, kinds in (
            (331.0, ["player", "wall"]),
            (329.0, ["wall", "player"]),
            (330.0, ["wall", "player"]),
        ):
            player = Player(x=480.0, y=player_y)
            with self.subTest(player_y=player_y):
                drawn = sorted_drawables(player, [wall])
                self.assertIsInstance(drawn, list)
                self.assertEqual([kind for kind, _ in drawn], kinds)
                for kind, item in drawn:
                    self.assertIs(item, player if kind == "player" else wall)

    def test_wall_depth_uses_bottom_not_center_or_far_edge(self):
        wall = Wall(400.0, 330.0, 220.0, 60.0)
        player = Player(x=480.0, y=350.0)
        self.assertEqual(
            [kind for kind, _ in sorted_drawables(player, [wall])],
            ["player", "wall"],
        )

    def test_multiple_walls_follow_ground_depth(self):
        near = Wall(700.0, 50.0, 80.0, 240.0)
        far = Wall(20.0, 430.0, 70.0, 10.0)
        middle = Wall(300.0, 200.0, 40.0, 80.0)
        player = Player(x=480.0, y=350.0)
        drawn = sorted_drawables(player, [near, far, middle])
        expected = [("wall", far), ("player", player),
                    ("wall", middle), ("wall", near)]
        self.assertEqual(len(drawn), len(expected))
        for actual, wanted in zip(drawn, expected):
            self.assertEqual(actual[0], wanted[0])
            self.assertIs(actual[1], wanted[1])

    def test_sorting_does_not_mutate_player_walls_or_input_order(self):
        player = Player(x=480.0, y=350.0, aim_angle=0.7, moved=True)
        walls = [Wall(600.0, 200.0, 40.0, 80.0),
                 Wall(100.0, 430.0, 90.0, 20.0)]
        original_walls = walls.copy()
        player_before = asdict(player)
        walls_before = [asdict(wall) for wall in walls]

        first = sorted_drawables(player, walls)
        second = sorted_drawables(player, walls)

        self.assertEqual(asdict(player), player_before)
        self.assertEqual([asdict(wall) for wall in walls], walls_before)
        self.assertEqual(len(walls), len(original_walls))
        for actual, original in zip(walls, original_walls):
            self.assertIs(actual, original)
        self.assertEqual(first, second)


class SpriteGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))

    def test_metadata_matches_png_canvas_and_valid_clip_and_pivot(self):
        image_path = METADATA_PATH.parent / self.metadata["image"]
        with image_path.open("rb") as image:
            header = image.read(24)
        self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(header[12:16], b"IHDR")
        canvas = struct.unpack(">II", header[16:24])
        self.assertEqual(tuple(self.metadata["canvas_size"]), canvas)

        left, top, width, height = self.metadata["clip_topleft"]
        for value in (left, top, width, height):
            self.assertIsInstance(value, int)
        self.assertGreaterEqual(left, 0)
        self.assertGreaterEqual(top, 0)
        self.assertGreater(width, 0)
        self.assertGreater(height, 0)
        self.assertLessEqual(left + width, canvas[0])
        self.assertLessEqual(top + height, canvas[1])
        pivot_x, pivot_y = self.metadata["foot_pivot_topleft"]
        self.assertLessEqual(left, pivot_x)
        self.assertLessEqual(pivot_x, left + width)
        self.assertLessEqual(top, pivot_y)
        self.assertLessEqual(pivot_y, top + height)

    def test_top_left_png_pivot_lands_on_screen_ground_point(self):
        # The pivot is 20px from the clip's left, 25px from its bottom.
        rectangle = sprite_rect(123.0, 456.0, (10, 20, 80, 100), (30, 95), 50)
        for actual, expected in zip(rectangle, (113.0, 443.5, 40.0, 50.0)):
            self.assertAlmostEqual(actual, expected, places=9)

        clip = self.metadata["clip_topleft"]
        pivot = self.metadata["foot_pivot_topleft"]
        foot = world_to_screen(480.0, 180.0)
        left, bottom, width, height = sprite_rect(
            *foot, clip, pivot, self.metadata["display_height"],
        )
        source_left_fraction = (pivot[0] - clip[0]) / clip[2]
        source_bottom_fraction = (clip[1] + clip[3] - pivot[1]) / clip[3]
        self.assertAlmostEqual(left + width * source_left_fraction, foot[0], places=9)
        self.assertAlmostEqual(bottom + height * source_bottom_fraction, foot[1], places=9)

    def test_sample_display_size_preserves_source_aspect_ratio(self):
        clip = self.metadata["clip_topleft"]
        rectangle = sprite_rect(
            640.0, 198.0, clip, self.metadata["foot_pivot_topleft"],
            self.metadata["display_height"],
        )
        self.assertEqual(self.metadata["display_height"], 128)
        self.assertEqual(self.metadata["sampling"], "nearest")
        self.assertAlmostEqual(rectangle[3], 128.0, places=9)
        self.assertAlmostEqual(rectangle[2] / rectangle[3], clip[2] / clip[3], places=9)

    def test_ground_translation_moves_sprite_without_changing_size_or_metadata(self):
        clip = self.metadata["clip_topleft"].copy()
        pivot = self.metadata["foot_pivot_topleft"].copy()
        arguments_before = (clip.copy(), pivot.copy())
        first = sprite_rect(640.0, 198.0, clip, pivot, 128)
        second = sprite_rect(517.75, 289.5, clip, pivot, 128)
        self.assertAlmostEqual(second[0] - first[0], -122.25, places=9)
        self.assertAlmostEqual(second[1] - first[1], 91.5, places=9)
        self.assertEqual(first[2:], second[2:])
        self.assertEqual((clip, pivot), arguments_before)


if __name__ == "__main__":
    unittest.main()
