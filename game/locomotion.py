"""R1-B ground-facing and walking poses, independent of rendering."""
from dataclasses import dataclass, field
import math


STRIDE_DISTANCE = 32.0
_ANGLE_TOLERANCE = 1e-12
_PHASE_TOLERANCE = 1e-12
_FACING_LIMIT = math.radians(50.0)
_DIRECTIONS = (
    ("front_right", -math.pi / 4),
    ("back_right", math.pi / 4),
    ("back_left", 3 * math.pi / 4),
    ("front_left", -3 * math.pi / 4),
)


def _finite(*values: float) -> bool:
    try:
        return all(math.isfinite(value) for value in values)
    except (TypeError, ValueError, OverflowError):
        return False


def select_facing(aim_angle: float, current: str | None = None) -> str:
    current_angle = next((angle for name, angle in _DIRECTIONS if name == current), None)
    if not _finite(aim_angle):
        return current if current_angle is not None else "front_right"
    angle = math.remainder(aim_angle, math.tau)
    if current_angle is not None:
        distance = abs(math.remainder(angle - current_angle, math.tau))
        if distance <= _FACING_LIMIT + _ANGLE_TOLERANCE:
            return current
    closest, best_distance = "front_right", math.inf
    for name, representative in _DIRECTIONS:
        distance = abs(math.remainder(angle - representative, math.tau))
        if distance < best_distance - _ANGLE_TOLERANCE:
            closest, best_distance = name, distance
    return closest


@dataclass
class Locomotion:
    facing: str = "front_right"
    phase: float = 0.0
    moving: bool = False
    _initialized: bool = field(default=False, init=False, repr=False)

    def update(self, aim_angle: float, dx: float, dy: float) -> None:
        self.moving = False
        if not _finite(aim_angle, dx, dy):
            return
        distance = math.hypot(dx, dy)
        if not math.isfinite(distance):
            return
        self.facing = select_facing(aim_angle, self.facing if self._initialized else None)
        self._initialized = True
        if distance > 1e-6:
            self.moving = True
            # Reduce before adding to preserve the old phase for large distances.
            self.phase = (self.phase + (distance % STRIDE_DISTANCE) / STRIDE_DISTANCE) % 1.0
            # Split distances must choose the same frame at half/full cycles.
            for boundary in (0.0, 0.5, 1.0):
                if abs(self.phase - boundary) <= _PHASE_TOLERANCE:
                    self.phase = boundary % 1.0
                    break

    @property
    def frame_index(self) -> int:
        if not self.moving:
            return 0
        return 1 if self.phase < 0.5 else 2
