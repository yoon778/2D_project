"""Corner routes around the same rectangular walls used for movement."""
from heapq import heappop, heappush
import math

if __package__:
    from .core import PLAYER_RADIUS, WORLD_HEIGHT, WORLD_WIDTH, wall_blocks
else:
    from core import PLAYER_RADIUS, WORLD_HEIGHT, WORLD_WIDTH, wall_blocks


def _corners(wall, padding=0.0):
    return [(x, y) for x in (wall.x - padding, wall.x + wall.width + padding)
            for y in (wall.y - padding, wall.y + wall.depth + padding)]


def _overlaps(point, wall):
    x, y = point
    dx = max(wall.x - x, 0.0, x - wall.x - wall.width)
    dy = max(wall.y - y, 0.0, y - wall.y - wall.depth)
    return dx * dx + dy * dy < PLAYER_RADIUS ** 2 - 1e-6


def can_walk_direct(start, end, walls):
    """Test swept circle clearance, including near a rounded wall corner."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length_squared = dx * dx + dy * dy
    west, east = min(start[0], end[0]) - PLAYER_RADIUS, max(start[0], end[0]) + PLAYER_RADIUS
    south, north = min(start[1], end[1]) - PLAYER_RADIUS, max(start[1], end[1]) + PLAYER_RADIUS
    for wall in walls:
        if wall.x > east or wall.x + wall.width < west or wall.y > north or wall.y + wall.depth < south:
            continue
        if wall_blocks(start, end, wall) or _overlaps(start, wall) or _overlaps(end, wall):
            return False
        if length_squared:
            for x, y in _corners(wall):
                fraction = ((x - start[0]) * dx + (y - start[1]) * dy) / length_squared
                if 0 < fraction < 1:
                    offset_x = x - start[0] - fraction * dx
                    offset_y = y - start[1] - fraction * dy
                    if offset_x * offset_x + offset_y * offset_y < PLAYER_RADIUS ** 2 - 1e-6:
                        return False
    return True


def find_route(start, target, walls, world_size=(WORLD_WIDTH, WORLD_HEIGHT)):
    """Shortest available route through clear wall corners."""
    if can_walk_direct(start, target, walls):
        return [target]

    radius = PLAYER_RADIUS
    nodes = [start, target]
    for wall in walls:
        nodes.extend((x, y) for x, y in _corners(wall, radius + 1)
                     if radius <= x <= world_size[0] - radius
                     and radius <= y <= world_size[1] - radius
                     and not any(_overlaps((x, y), other) for other in walls))

    distances = {0: 0.0}
    previous = {}
    queue = [(0.0, 0)]
    while queue:
        distance, index = heappop(queue)
        if distance != distances[index]:
            continue
        if index == 1:
            route = []
            while index:
                route.append(nodes[index])
                index = previous[index]
            return route[::-1]
        for neighbor in range(1, len(nodes)):
            if neighbor == index:
                continue
            cost = distance + math.dist(nodes[index], nodes[neighbor])
            if cost < distances.get(neighbor, math.inf) and can_walk_direct(nodes[index], nodes[neighbor], walls):
                distances[neighbor] = cost
                previous[neighbor] = index
                heappush(queue, (cost, neighbor))
    return []
