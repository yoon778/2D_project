import math
import unittest

from game.core import Wall
from game.flashlight import Flashlight, HALF_ANGLE


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
