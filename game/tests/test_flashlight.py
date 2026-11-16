import math
import unittest

from game.core import Wall
from game.flashlight import Flashlight, HALF_ANGLE, LightField, feathered_beam_mesh, nearby_glow, nearby_glow_strength


class FlashlightSpanTests(unittest.TestCase):
    def test_beam_edge_can_light_only_side_of_sprite(self):
        origin = (200, 100)
        depth = 240
        edge = 310
        angle = math.atan2(depth - origin[1], edge - origin[0]) - HALF_ANGLE
        (left, right), = Flashlight(origin, angle, []).spans_at(depth)
        self.assertAlmostEqual(left, edge)
        self.assertGreater(right, edge + 10)

    def test_wall_shadow_splits_beam_into_two_spans(self):
        wall = Wall(190, 180, 20, 20)
        left, right = Flashlight((200, 100), math.pi / 2, [wall]).spans_at(260)
        self.assertLess(left[0], 170)
        self.assertAlmostEqual(left[1], 180, places=2)
        self.assertAlmostEqual(right[0], 220, places=2)
        self.assertGreater(right[1], 230)

    def test_streetlight_survives_turning_away_but_preserves_wall_shadow(self):
        wall = Wall(190, 180, 20, 20)
        lamp = Flashlight((200, 100), 0, [wall], radius=185, half_angle=math.pi)
        away = Flashlight((200, 60), -math.pi / 2, [wall])
        lights = LightField((away, lamp))

        self.assertTrue(lights.contains((240, 260)))
        self.assertFalse(lights.contains((200, 260)))
        left, right = lights.spans_at(260)
        self.assertLess(left[1], 200)
        self.assertGreater(right[0], 200)
        self.assertTrue(right[0] < 240 < right[1])

        toward = Flashlight((210, 60), math.pi / 2, [wall])
        self.assertEqual(len(LightField((toward, lamp)).spans_at(130)), 1)

    def test_nearby_glow_covers_all_directions_up_to_110_pixels(self):
        glow = nearby_glow((200, 150), (), (400, 300))
        for point in ((90, 150), (310, 150), (200, 40), (200, 260)):
            with self.subTest(point=point):
                self.assertTrue(glow.contains(point))
        for point in ((89, 150), (311, 150), (200, 39), (200, 261)):
            with self.subTest(point=point):
                self.assertFalse(glow.contains(point))

    def test_nearby_glow_uses_only_local_walls_and_preserves_their_shadows(self):
        near = Wall(210, 85, 2, 30)
        overlapping = Wall(130, 95, 22, 10)
        far = Wall(320, 85, 20, 30)
        glow = nearby_glow((200, 100), (near, overlapping, far), (400, 300))

        self.assertEqual(glow.walls, (near, overlapping))
        self.assertTrue(glow.contains((185, 100)))
        self.assertFalse(glow.contains((225, 100)))
        self.assertTrue(any(wall is near for _, wall in glow.outline()))
        self.assertFalse(any(left <= 225 <= right for left, right in glow.spans_at(100)))

    def test_nearby_glow_feathers_evenly_including_the_angular_seam(self):
        origin = (200, 150)
        glow = nearby_glow(origin, (), (400, 300))
        vertices, _ = feathered_beam_mesh(glow, glow.outline())
        midpoint_light = round(255 * nearby_glow_strength(55))
        for point in ((145, 150), (255, 150), (200, 95), (200, 205)):
            self.assertEqual({alpha for vertex, alpha in vertices if math.dist(point, vertex) < 1e-8}, {midpoint_light})
        self.assertEqual(nearby_glow_strength(110), 0)
        self.assertTrue(all(alpha == 0 for point, alpha in vertices if math.dist(point, origin) >= 109.999))

    def test_beam_feather_fades_sides_and_tip_while_retaining_the_core(self):
        beam = Flashlight((400, 360), 0, ())
        vertices, _ = feathered_beam_mesh(beam, beam.outline())

        def opacity_at(distance, degrees):
            angle = math.radians(degrees)
            sample = (400 + distance * math.cos(angle), 360 + distance * math.sin(angle))
            return next(opacity for point, opacity in vertices if math.dist(point, sample) < 1e-8)

        self.assertEqual(opacity_at(0, 0), 255)
        for direction in (-1, 1):
            self.assertEqual(opacity_at(284, direction * 32), 255)
            self.assertAlmostEqual(opacity_at(284, direction * 36), 127.5, delta=0.5)
            self.assertEqual(opacity_at(284, direction * 40), 0)
        self.assertEqual(opacity_at(284, 0), 255)
        self.assertGreater(opacity_at(298, 0), opacity_at(312, 0))
        self.assertGreater(opacity_at(312, 0), opacity_at(326, 0))
        self.assertEqual(opacity_at(340, 0), 0)

    def test_feather_mesh_matches_the_wall_clipped_outline(self):
        wall = Wall(500, 300, 30, 120)
        beam = Flashlight((400, 360), 0, (wall,))
        outline = beam.outline()
        vertices, indices = feathered_beam_mesh(beam, outline)
        opacities = dict(vertices)
        self.assertTrue(all(point in opacities for point, _ in outline))
        self.assertEqual(opacities[(500, 360)], 255)
        self.assertNotIn((740, 360), opacities)

        def area(a, b, c):
            return abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) / 2

        original_area = sum(area(beam.origin, a, b) for (a, _), (b, _) in zip(outline, outline[1:]))
        mesh_area = sum(area(*(vertices[index][0] for index in indices[start:start + 3]))
                        for start in range(0, len(indices), 3))
        self.assertAlmostEqual(original_area, mesh_area, places=7)
