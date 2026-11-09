"""Ground-plane flashlight visibility and wall-clipped beam outline."""
from functools import cached_property
import math

if __package__:
    from .core import WORLD_HEIGHT, WORLD_WIDTH, wall_blocks, wall_entry
else:
    from core import WORLD_HEIGHT, WORLD_WIDTH, wall_blocks, wall_entry


RANGE = 340.0
HALF_ANGLE = math.radians(40)
_ARC_STEPS = 40
_CORNER_OFFSET = 1e-5


class Flashlight:
    def __init__(self, origin, angle, walls, world_size=(WORLD_WIDTH, WORLD_HEIGHT), *,
                 radius=RANGE, half_angle=HALF_ANGLE):
        self.origin = origin
        self.angle = angle
        self.walls = walls
        self.world_size = world_size
        self.radius = radius
        self.half_angle = half_angle

    def contains(self, point):
        dx, dy = point[0] - self.origin[0], point[1] - self.origin[1]
        if math.hypot(dx, dy) > self.radius + 1e-9:
            return False
        if (dx or dy) and abs(math.remainder(math.atan2(dy, dx) - self.angle, math.tau)) > self.half_angle + 1e-9:
            return False
        return not any(wall_blocks(self.origin, point, wall) for wall in self.walls)

    def outline(self):
        return self._outline

    def spans_at(self, y):
        """Return lit horizontal spans at the depth of an upright sprite."""
        if abs(y - self.origin[1]) > self.radius:
            return ()
        intersections = []
        points = (self.origin, *(point for point, _ in self._outline), self.origin)
        for (ax, ay), (bx, by) in zip(points, points[1:]):
            if min(ay, by) <= y < max(ay, by):
                intersections.append(ax + (bx - ax) * (y - ay) / (by - ay))
        intersections.sort()
        return tuple(zip(intersections[::2], intersections[1::2]))

    @cached_property
    def _outline(self):
        """Beam edge samples plus rays on both sides of every wall corner."""
        x, y = self.origin
        limit = self.half_angle
        steps = _ARC_STEPS * 2 if limit == math.pi else _ARC_STEPS
        angles = {-limit + i * 2 * limit / steps for i in range(steps + 1)}
        for wall in self.walls:
            for wx in (wall.x, wall.x + wall.width):
                for wy in (wall.y, wall.y + wall.depth):
                    angle = math.remainder(math.atan2(wy - y, wx - x) - self.angle, math.tau)
                    candidates = (angle - _CORNER_OFFSET, angle, angle + _CORNER_OFFSET)
                    if limit == math.pi:
                        angles.update(math.remainder(a, math.tau) for a in candidates)
                    else:
                        angles.update(a for a in candidates if -limit < a < limit)
        return [self._cast(self.angle + angle) for angle in sorted(angles)]

    def _cast(self, angle):
        x, y = self.origin
        dx, dy = math.cos(angle), math.sin(angle)
        length = self.radius
        for position, velocity, limit in zip(self.origin, (dx, dy), self.world_size):
            if abs(velocity) > 1e-12:
                boundary = limit if velocity > 0 else 0.0
                length = min(length, (boundary - position) / velocity)
        end = (x + dx * length, y + dy * length)
        nearest, hit = 1.0, None
        for wall in self.walls:
            entry = wall_entry(self.origin, end, wall)
            if entry is not None and entry <= nearest:
                nearest, hit = entry, wall
        return (x + dx * length * nearest, y + dy * length * nearest), hit


class LightField:
    """Ground visibility contributed by the hand-held and fixed lights."""

    def __init__(self, lights):
        self.lights = lights

    def contains(self, point):
        return any(light.contains(point) for light in self.lights)

    def spans_at(self, y):
        spans = sorted(span for light in self.lights for span in light.spans_at(y))
        merged = []
        for left, right in spans:
            if merged and left <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(right, merged[-1][1]))
            else:
                merged.append((left, right))
        return merged
