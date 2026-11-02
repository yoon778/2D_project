"""Flashlight boundary, clipped at the first building hit by each ray."""
from math import atan2, cos, pi, sin, tau
from core import HEIGHT, WIDTH


def flashlight_polygon(game):
    player = game.player
    half = game.flashlight_half_angle
    offsets = {-half + 2 * half * index / 100 for index in range(101)}
    # Extra rays either side of corners prevent light leaking behind buildings.
    for wall in game.walls:
        for x, y in ((wall.x, wall.y), (wall.x + wall.w, wall.y),
                     (wall.x, wall.y + wall.h), (wall.x + wall.w, wall.y + wall.h)):
            offset = (atan2(y - player.y, x - player.x) - player.angle + pi) % tau - pi
            if -half <= offset <= half:
                offsets.update(max(-half, min(half, offset + epsilon))
                               for epsilon in (-0.00001, 0.0, 0.00001))
    boundary = []
    for offset in sorted(offsets):
        dx, dy = cos(player.angle + offset), sin(player.angle + offset)
        distance = game.flashlight_range
        for origin, direction, maximum in ((player.x, dx, WIDTH - 1),
                                            (player.y, dy, HEIGHT - 1)):
            if abs(direction) > 1e-10:
                distance = min(distance, ((maximum if direction > 0 else 0) - origin) / direction)
        for wall in game.walls:
            near, far = 0.0, distance
            for origin, direction, low, high in (
                (player.x, dx, wall.x, wall.x + wall.w),
                (player.y, dy, wall.y, wall.y + wall.h),
            ):
                if abs(direction) < 1e-10:
                    if not low <= origin <= high:
                        near = float("inf")
                        break
                else:
                    first, last = sorted(((low - origin) / direction,
                                          (high - origin) / direction))
                    near, far = max(near, first), min(far, last)
            if far >= near:
                distance = min(distance, near)
        boundary.append((max(0.0, min(WIDTH - 1, player.x + dx * distance)),
                         max(0.0, min(HEIGHT - 1, player.y + dy * distance))))
    return boundary
