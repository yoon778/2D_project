"""R1-A ground movement; independent of rendering and SDL."""
from collections.abc import Sequence
from dataclasses import dataclass
import math


WORLD_WIDTH = 960.0
WORLD_HEIGHT = 720.0
WALK_SPEED = 90.0
PLAYER_RADIUS = 14.0
_MAX_MOVE_DT = 10.0


@dataclass
class Wall:
    x: float
    y: float
    width: float
    depth: float


@dataclass
class Player:
    x: float = 480.0
    y: float = 180.0
    aim_angle: float = math.pi / 4
    moved: bool = False


def _move_axis(start: float, other: float, delta: float, limit: float,
               walls: Sequence[Wall], horizontal: bool) -> float:
    target = max(PLAYER_RADIUS, min(limit - PLAYER_RADIUS, start + delta))
    for wall in walls:
        low, size, across, span = (
            (wall.x, wall.width, wall.y, wall.depth) if horizontal
            else (wall.y, wall.depth, wall.x, wall.width)
        )
        separation = max(across - other, other - across - span, 0.0)
        if separation >= PLAYER_RADIUS:
            continue
        # Sweep to circle/rectangle contact, including the rounded corners.
        reach = math.sqrt(PLAYER_RADIUS ** 2 - separation ** 2)
        near, far = low - reach, low + size + reach
        if delta > 0 and start <= near:
            target = min(target, near)
        elif delta < 0 and start >= far:
            target = max(target, far)
    return target


def move_player(player: Player, axis_x: float, axis_y: float,
                dt: float, walls: Sequence[Wall], *, world_size=(WORLD_WIDTH, WORLD_HEIGHT)) -> None:
    """Move a valid ground position; invalid dt leaves it unchanged."""
    player.moved = False
    if not isinstance(dt, (int, float)) or not math.isfinite(dt) or dt <= 0:
        return
    length = math.hypot(axis_x, axis_y)
    if length == 0 or not math.isfinite(length):
        return
    velocity_x = axis_x / length * WALK_SPEED
    velocity_y = axis_y / length * WALK_SPEED
    origin = (player.x, player.y)
    # UI uses <= 0.05 s; cap oversized calls to keep the work bounded.
    remaining = min(dt, _MAX_MOVE_DT)
    while remaining > 0:
        # Short axis sweeps retain sliding behavior even for a long update.
        tick = min(remaining, PLAYER_RADIUS / (2 * WALK_SPEED))
        before = (player.x, player.y)
        player.x = _move_axis(player.x, player.y, velocity_x * tick,
                              world_size[0], walls, True)
        player.y = _move_axis(player.y, player.x, velocity_y * tick,
                              world_size[1], walls, False)
        remaining -= tick
        if (player.x, player.y) == before:
            # Constant input cannot escape this static contact in later ticks.
            break
    player.moved = (player.x, player.y) != origin


def aim_player(player: Player, target_x: float, target_y: float, *, max_turn: float = math.inf) -> None:
    """Aim on the ground plane without moving or changing the moved flag."""
    if not math.isfinite(target_x) or not math.isfinite(target_y):
        return
    dx, dy = target_x - player.x, target_y - player.y
    if dx != 0 or dy != 0:
        target = math.atan2(dy, dx)
        if max_turn == math.inf:
            player.aim_angle = target
            return
        delta = math.remainder(target - player.aim_angle, math.tau)
        if abs(delta) <= max_turn:
            player.aim_angle = target
        else:
            player.aim_angle = math.remainder(player.aim_angle + math.copysign(max_turn, delta), math.tau)


def wall_entry(start, end, wall: Wall) -> float | None:
    """Fraction along a closed segment where it first touches a wall."""
    enter, leave = 0.0, 1.0
    epsilon = 1e-12
    for origin, delta, low, high in (
        (start[0], end[0] - start[0], wall.x, wall.x + wall.width),
        (start[1], end[1] - start[1], wall.y, wall.y + wall.depth),
    ):
        if abs(delta) <= epsilon:
            if origin < low - epsilon or origin > high + epsilon:
                return None
        else:
            first, last = sorted(((low - origin) / delta, (high - origin) / delta))
            enter, leave = max(enter, first), min(leave, last)
            if enter > leave + epsilon:
                return None
    return enter


def wall_blocks(start, end, wall: Wall) -> bool:
    return wall_entry(start, end, wall) is not None
