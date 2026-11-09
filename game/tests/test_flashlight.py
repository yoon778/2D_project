import math
import unittest

from game.core import Wall
from game.flashlight import Flashlight, HALF_ANGLE, LightField


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
