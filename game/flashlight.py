"""Ground-plane flashlight visibility and wall-clipped beam outline."""
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
    def __init__(self, origin, angle, walls):
        self.origin = origin
        self.angle = angle
        self.walls = walls

    def contains(self, point):
        dx, dy = point[0] - self.origin[0], point[1] - self.origin[1]
        if math.hypot(dx, dy) > RANGE + 1e-9:
            return False
        if (dx or dy) and abs(math.remainder(math.atan2(dy, dx) - self.angle, math.tau)) > HALF_ANGLE + 1e-9:
            return False
        return not any(wall_blocks(self.origin, point, wall) for wall in self.walls)

    def outline(self):
        """Beam edge samples plus rays on both sides of every wall corner."""
        x, y = self.origin
        angles = {-HALF_ANGLE + i * 2 * HALF_ANGLE / _ARC_STEPS for i in range(_ARC_STEPS + 1)}
        for wall in self.walls:
            for wx in (wall.x, wall.x + wall.width):
                for wy in (wall.y, wall.y + wall.depth):
                    angle = math.remainder(math.atan2(wy - y, wx - x) - self.angle, math.tau)
                    angles.update(a for a in (angle - _CORNER_OFFSET, angle, angle + _CORNER_OFFSET)
                                  if -HALF_ANGLE < a < HALF_ANGLE)
        return [self._cast(self.angle + angle) for angle in sorted(angles)]

    def _cast(self, angle):
        x, y = self.origin
        dx, dy = math.cos(angle), math.sin(angle)
        length = RANGE
        for position, velocity, limit in ((x, dx, WORLD_WIDTH), (y, dy, WORLD_HEIGHT)):
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
