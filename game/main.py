"""Dead Route alley delivery, combat and flashlight rendering."""
from __future__ import annotations

import argparse
import ctypes
import math
from pathlib import Path
import time

import pico2d.pico2d as p

from core import WORLD_WIDTH, WORLD_HEIGHT, aim_player, wall_blocks
from combat import CombatWorld, MAX_STAMINA
from combat_visual import CombatVisual
from delivery import DELIVERY_CONTRACTS, TOWN_ROADS, DeliveryWorld, NeighborhoodWall
from flashlight import Flashlight, LightField
from locomotion import Locomotion, select_facing
from player_visual import PlayerVisual, load_atlas
from spatial_audio import ZombieAudio
import opening

WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
GROUND_X = 160.0
GROUND_Y = 90.0
GROUND_SCALE_Y = 0.60
WALL_HEIGHT = 110
DELIVERY_CHARACTER_SCALE = 0.60
DELIVERY_KEYS = {p.SDLK_1: 0, p.SDLK_KP_1: 0, p.SDLK_2: 1, p.SDLK_KP_2: 1}
BASE_DIR = Path(__file__).resolve().parent
TRASH_CAN_PATH = BASE_DIR / "assets/props/alley-trash-can.png"
NEIGHBORHOOD_PATH = BASE_DIR / "assets/neighborhood"
WALL_TEXTURE_SIZES = {
    "west-house": [70, 112],
    "east-house": [138, 115],
    "west-house-side": [56, 55],
    "east-house-side": [56, 55],
    "workshop": [100, 100],
    "fence": [50, 23],
    "shop": [130, 103],
    "bus-stop": [70, 50],
    "parked-car": [56, 31],
    "abandoned-car": [56, 31],
    "dumpster": [30, 24],
}
PROP_TEXTURE_SIZES = {
    "mailbox": [10, 24],
    "planter": [13, 15],
    "bicycle": [23, 16],
    "trash-bags": [15, 12],
    "metal-bin": [13, 21],
    "recycling-bin": [14, 22],
}
HOUSE_FOUNDATION_HEIGHT = 8
ROOF_LIGHT_BAND = 24
GROUND_NEUTRAL = 144
STREETLIGHT_RADIUS = 185.0
TRASH_CAN_POSITION = (365.0, 300.0)
WHITE = (231, 236, 231)
TEAL = (86, 225, 194)
ORANGE = (255, 182, 78)
HIT_MARK_DURATION = 0.06
SPRINT_PULSE_DURATION = 0.24
PULSE_RING = tuple((math.cos(i * math.tau / 24), math.sin(i * math.tau / 24)) for i in range(25))
ZOMBIE_MARKS = {"chase": ("!", ORANGE), "investigate": ("?", TEAL), "search": ("?", TEAL)}
TURN_SPEED = math.radians(450)
SHAKE_DURATIONS = {3: 0.08, 4: 0.10}
SHAKE_DIRECTIONS = ((1, 0), (-1, 1), (1, -1), (-1, 0))


def world_to_screen(x, y, camera=(0.0, 0.0)):
    return GROUND_X + x - camera[0], GROUND_Y + GROUND_SCALE_Y * (y - camera[1])


def screen_to_world(x, y, camera=(0.0, 0.0)):
    return x - GROUND_X + camera[0], (y - GROUND_Y) / GROUND_SCALE_Y + camera[1]


def sdl_to_world(x, y, camera=(0.0, 0.0)):
    return screen_to_world(x, WINDOW_HEIGHT - 1 - y, camera)


def current_cursor():
    mouse_window = p.SDL_GetMouseFocus()
    if not mouse_window or p.SDL_GetWindowID(mouse_window) != p.SDL_GetWindowID(p.window):
        return None
    x, y = ctypes.c_int(), ctypes.c_int()
    p.SDL_GetMouseState(ctypes.byref(x), ctypes.byref(y))
    return x.value, y.value


def sorted_drawables(player, walls, zombie=None, *, zombies=(), prop=None, station=None, lamps=(), street_props=()):
    # Stable ties: fixed props precede walls and characters at the same ground y.
    objects = [("prop", prop)] if prop is not None else []
    if station is not None:
        objects.append(("station", station))
    objects.extend(("lamp", position) for position in lamps)
    objects.extend(("street-prop", decoration) for decoration in street_props)
    objects.extend(("wall", wall) for wall in walls)
    if zombie is not None:
        objects.append(("zombie", zombie))
    objects.extend(("zombie", enemy) for enemy in zombies)
    objects.append(("player", player))
    return sorted(objects, key=lambda item: -(item[1][1] if item[0] in ("prop", "station", "lamp") else item[1].y))


def light_screen_rows(lights, project):
    """Rasterize the same projected outlines used by the ground light."""
    rows = [[] for _ in range(WINDOW_HEIGHT)]
    for light in lights:
        points = [project(*point) for point in (light.origin, *(point for point, _ in light.outline()))]
        crossings = {}
        for (ax, ay), (bx, by) in zip(points, (*points[1:], points[0])):
            ay, by = WINDOW_HEIGHT - 1 - ay, WINDOW_HEIGHT - 1 - by
            start = max(0, math.ceil(min(ay, by) - .5))
            end = min(WINDOW_HEIGHT, math.ceil(max(ay, by) - .5))
            if start >= end:
                continue
            slope = (bx - ax) / (by - ay)
            for row in range(start, end):
                x = math.ceil(ax + (row + .5 - ay) * slope - .5)
                crossings.setdefault(row, []).append(max(0, min(WINDOW_WIDTH, x)))
        for row, edges in crossings.items():
            edges.sort()
            rows[row].extend((left, right) for left, right in zip(edges[::2], edges[1::2]) if left < right)
    for row, spans in enumerate(rows):
        merged = []
        for left, right in sorted(spans):
            if merged and left <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], right))
            else:
                merged.append((left, right))
        rows[row] = merged
    return rows


def mouse_target(world, visual, mouse_x, mouse_y, light=None, camera=(0.0, 0.0), shake=(0, 0)):
    screen_y = WINDOW_HEIGHT - 1 - mouse_y
    for zombie in sorted(world.zombies, key=lambda enemy: enemy.y):
        position = (zombie.x, zombie.y)
        x, y = world_to_screen(*position, camera)
        if not visual.zombie_contains(zombie, x + shake[0], y + shake[1], mouse_x, screen_y):
            continue
        if light is not None:
            world_x, depth = screen_to_world(mouse_x + .5 - shake[0], screen_y - .5 - shake[1], camera)
            if not any(left <= world_x < right for left, right in light.spans_at(depth)):
                continue
        # A wall drawn in front can cover the upper part of a lit sprite.
        wx, wy = mouse_x - shake[0], screen_y - shake[1]
        for wall in world.walls:
            left, bottom = world_to_screen(wall.x, wall.y, camera)
            if wall.y < zombie.y and wall_covers(wall, left, bottom, wx, wy):
                break
        else:
            return position
    return sdl_to_world(mouse_x, mouse_y, camera)


def wall_height(wall):
    return wall.height if isinstance(wall, NeighborhoodWall) else WALL_HEIGHT


def house_planes(wall, x, y):
    depth = wall.depth * GROUND_SCALE_Y
    inset = round(min(wall.width * .26, depth * .42))
    near_right = x + wall.width - inset
    far_right = x + wall.width
    top = y + wall.height
    return (
        ((x, y), (near_right, y), (near_right, top), (x, top)),
        ((near_right, y), (far_right, y + depth), (far_right, top + depth), (near_right, top)),
        ((x, top), (near_right, top), (far_right, top + depth), (x + inset, top + depth)),
    )


def wall_covers(wall, left, bottom, x, y):
    oblique = isinstance(wall, NeighborhoodWall) and wall.oblique
    if oblique:
        # SDL fills triangles at the pixel center.
        x, y = x + .5, y + .5
    if not (left <= x < left + wall.width and bottom <= y < bottom + wall_height(wall) + wall.depth * GROUND_SCALE_Y):
        return False
    if not oblique:
        return True
    if y < bottom + wall.depth * GROUND_SCALE_Y + HOUSE_FOUNDATION_HEIGHT:
        return True
    # The projected house planes are convex and ordered counterclockwise.
    return any(all((bx - ax) * (y - ay) >= (by - ay) * (x - ax)
                   for (ax, ay), (bx, by) in zip(plane, (*plane[1:], plane[0])))
               for plane in house_planes(wall, left, bottom))


def wall_edge_spans(wall, outline, axis, boundary):
    start = end = None
    for point, hit in outline:
        if hit is wall and abs(point[axis] - boundary) < 1e-7:
            position = point[1 - axis]
            if start is None:
                start = position
            end = position
        elif start is not None:
            if start != end:
                yield sorted((start, end))
            start = end = None
    if start is not None and start != end:
        yield sorted((start, end))


def quad(x, y, width, height):
    return ((x, y), (x + width, y), (x + width, y + height), (x, y + height))


def clip_wall_plane(points, bounds, mask):
    # Each wall face is a parallelogram. Clip in its UV space to keep the texture aligned.
    (ax, ay), (bx, by), _, (dx, dy) = points
    ux, uy, vx, vy = bx - ax, by - ay, dx - ax, dy - ay
    determinant = ux * vy - uy * vx
    polygon = [(((x - ax) * vy - (y - ay) * vx) / determinant,
                (ux * (y - ay) - uy * (x - ax)) / determinant) for x, y in mask]
    left, near, right, far = bounds
    for axis, limit, sign in ((0, left, 1), (0, right, -1), (1, near, 1), (1, far, -1)):
        if not polygon:
            break
        clipped = []
        for a, b in zip((polygon[-1], *polygon[:-1]), polygon):
            start, end = (a[axis] - limit) * sign, (b[axis] - limit) * sign
            if (start < 0) != (end < 0):
                t = start / (start - end)
                clipped.append(tuple(x + (y - x) * t for x, y in zip(a, b)))
            if end >= 0:
                clipped.append(b)
        polygon = clipped
    return polygon


def rectangle(x, y, width, height, color, filled=True):
    p.draw_rectangle(x, y, x + width, y + height, *color, filled=filled)


def cross(x, y, color, size=5):
    p.draw_line(x - size, y, x + size, y, *color)
    p.draw_line(x, y - size, x, y + size, *color)


class Renderer:
    def __init__(self):
        self.font = None
        self.player_visual = None
        self.combat_visual = None
        self.trash_can = None
        self.neighborhood_ground = None
        self.neighborhood_walls = {}
        self.street_prop_images = {}
        self.streetlamp_image = None
        self.streetlights = ()
        self.combat = None
        self.delivery = None
        self.cursor = None
        self.light = None
        self.camera = (0.0, 0.0)
        self.choosing_delivery = False
        self.map_open = False
        self.shake_remaining = 0.0
        self.shake_strength = 0
        self.shake_offset = (0, 0)
        self.sprint_pulse = None
        self.sprint_pulse_remaining = 0.0
        try:
            font_path = Path(p.__file__).parent / "data/ConsolaMalgun.ttf"
            self.font = p.load_font(str(font_path), 18)
            self.player_visual = PlayerVisual()
            self.combat_visual = CombatVisual()
            self.trash_can = p.load_image(str(TRASH_CAN_PATH))
            if p.SDL_SetTextureScaleMode(self.trash_can.texture, p.SDL_ScaleModeNearest) != 0:
                raise RuntimeError(f"Trash can nearest sampling failed: {p.SDL_GetError()!r}")
        except Exception:
            self.close()
            raise

    def load_neighborhood(self):
        world_w, world_h = self.delivery.world_size
        self.neighborhood_ground = load_atlas(NEIGHBORHOOD_PATH / "ground.png",
                                              [round(world_w / 2), round(world_h * GROUND_SCALE_Y / 2)])
        for wall in self.delivery.walls:
            if isinstance(wall, NeighborhoodWall) and wall.texture not in self.neighborhood_walls:
                self.neighborhood_walls[wall.texture] = load_atlas(
                    NEIGHBORHOOD_PATH / f"{wall.texture}.png", WALL_TEXTURE_SIZES[wall.texture])
            if isinstance(wall, NeighborhoodWall) and wall.oblique:
                key = f"{wall.texture}-side"
                if key not in self.neighborhood_walls:
                    self.neighborhood_walls[key] = load_atlas(NEIGHBORHOOD_PATH / f"{key}.png", WALL_TEXTURE_SIZES[key])
        for image in self.neighborhood_walls.values():
            if p.SDL_SetTextureBlendMode(image.texture, p.SDL_BLENDMODE_BLEND) != 0:
                raise RuntimeError(f"Wall blend mode failed: {p.SDL_GetError()!r}")
        self.street_prop_images = {
            key: load_atlas(NEIGHBORHOOD_PATH / f"{key}.png", size) for key, size in PROP_TEXTURE_SIZES.items()
        }
        self.streetlamp_image = load_atlas(NEIGHBORHOOD_PATH / "streetlamp.png", [14, 54])
        self.reset_streetlights()

    def reset_streetlights(self):
        radius = STREETLIGHT_RADIUS
        lights = []
        for x, y in self.delivery.streetlights:
            walls = [wall for wall in self.delivery.walls
                     if x - radius <= wall.x + wall.width and wall.x <= x + radius
                     and y - radius <= wall.y + wall.depth and wall.y <= y + radius]
            lights.append(Flashlight((x, y), 0, walls, self.delivery.world_size,
                                     radius=radius, half_angle=math.pi))
        self.streetlights = tuple(lights)

    def streetlights_in_view(self):
        for light in self.streetlights:
            x, y = self.project(*light.origin)
            radius_y = light.radius * GROUND_SCALE_Y
            if -light.radius <= x <= WINDOW_WIDTH + light.radius and -radius_y <= y <= WINDOW_HEIGHT + radius_y:
                yield light

    def close(self):
        self.street_prop_images.clear()
        self.streetlamp_image = None
        self.neighborhood_ground = None
        self.neighborhood_walls.clear()
        self.trash_can = None
        if self.combat_visual is not None:
            self.combat_visual.close()
            self.combat_visual = None
        if self.player_visual is not None:
            self.player_visual.close()
            self.player_visual = None
        if self.font is not None:
            if self.font.font:
                p.TTF_CloseFont(self.font.font)
                self.font.font = None
            self.font = None

    def update_shake(self, dt, strength=0):
        if strength:
            self.shake_strength = strength
            self.shake_remaining = SHAKE_DURATIONS[strength]
        else:
            self.shake_remaining = max(0.0, self.shake_remaining - dt)
        self.shake_offset = (0, 0)
        if self.shake_remaining > 0:
            duration = SHAKE_DURATIONS[self.shake_strength]
            phase = int((duration - self.shake_remaining) / 0.014)
            dx, dy = SHAKE_DIRECTIONS[phase % len(SHAKE_DIRECTIONS)]
            amplitude = round(self.shake_strength * self.shake_remaining / duration)
            self.shake_offset = (dx * amplitude, dy * amplitude)

    def project(self, x, y):
        sx, sy = world_to_screen(x, y, self.camera)
        dx, dy = self.shake_offset
        return sx + dx, sy + dy

    def follow(self, player):
        if self.delivery is not None:
            width, height = self.delivery.world_size
            self.camera = (min(max(0.0, player.x - WORLD_WIDTH / 2), width - WORLD_WIDTH),
                           min(max(0.0, player.y - WORLD_HEIGHT / 2), height - WORLD_HEIGHT))

    def draw_delivery_selection(self):
        p.SDL_SetRenderDrawColor(p.renderer, 14, 20, 23, 255)
        p.SDL_RenderClear(p.renderer)
        rectangle(342, 178, 596, 364, (27, 39, 41))
        rectangle(342, 178, 596, 364, (91, 112, 112), filled=False)
        self.font.draw(378, 507, "DEAD ROUTE  |  배달 선택", TEAL)
        self.font.draw(378, 472, "이번에 전달할 택배의 목적지를 고르세요", WHITE)
        for index, contract in enumerate(DELIVERY_CONTRACTS, start=1):
            bottom = 360 - (index - 1) * 102
            accent = ORANGE if index == 1 else TEAL
            rectangle(378, bottom, 524, 80, (18, 29, 32))
            rectangle(378, bottom, 524, 80, (91, 112, 112), filled=False)
            self.font.draw(398, bottom + 55, f"[{index}]  {contract.name}", accent)
            self.font.draw(398, bottom + 25, contract.description, WHITE)
        self.font.draw(378, 216, "1 / 2 선택  ·  Esc 종료", WHITE)

    def draw_map(self, player):
        world = self.delivery
        width, height = world.world_size
        scale = min(792 / width, 528 / height)
        left = 64 + (792 - width * scale) / 2
        bottom = 104 + (528 - height * scale) / 2
        right = left + width * scale
        top = bottom + height * scale
        ink = (14, 20, 23)
        panel = (27, 39, 41)
        border = (91, 112, 112)
        main_color = (170, 145, 106)
        alley_color = (99, 132, 130)
        wreck_color = (177, 101, 77)
        building_color = (20, 30, 34)
        landmark_color = (178, 201, 195)

        def map_point(x, y):
            return left + x * scale, bottom + y * scale

        def heading(x, y, angle):
            dx, dy = math.cos(angle), math.sin(angle)
            tip_x, tip_y = x + 16 * dx, y + 16 * dy
            p.draw_line(x, y, tip_x, tip_y, *WHITE)
            for side in (-1, 1):
                p.draw_line(tip_x, tip_y, tip_x - 6 * dx - 4 * dy * side,
                            tip_y - 6 * dy + 4 * dx * side, *WHITE)
            rectangle(x - 4, y - 4, 8, 8, ink)
            rectangle(x - 2, y - 2, 4, 4, WHITE)

        p.SDL_SetRenderDrawColor(p.renderer, *ink, 255)
        p.SDL_RenderClear(p.renderer)
        rectangle(left, bottom, right - left, top - bottom, (41, 56, 57))
        for roads, color in ((TOWN_ROADS["alleys"], alley_color),
                             (TOWN_ROADS["main"], main_color),
                             ((TOWN_ROADS["main_detour"],), alley_color)):
            for road in roads:
                points = road["points"]
                half_width = road["width"] / 2
                for (ax, ay), (bx, by) in zip(points, points[1:]):
                    west = max(0, min(ax, bx) - half_width)
                    south = max(0, min(ay, by) - half_width)
                    east = min(width, max(ax, bx) + half_width)
                    north = min(height, max(ay, by) + half_width)
                    if west < east and south < north:
                        x, y = map_point(west, south)
                        rectangle(x, y, (east - west) * scale, (north - south) * scale, color)

        landmarks = []
        landmark_labels = {"shop": "상점", "bus-stop": "정류장"}
        for wall in world.walls:
            x, y = map_point(wall.x, wall.y)
            w, h = wall.width * scale, wall.depth * scale
            texture = getattr(wall, "texture", None)
            label = landmark_labels.get(texture)
            fill = wreck_color if texture == "abandoned-car" else building_color
            rectangle(x, y, w, h, fill)
            rectangle(x, y, w, h, landmark_color if label else border, filled=False)
            if label:
                landmarks.append((label, x + w / 2, y + h))

        for label, anchor_x, anchor_y in landmarks:
            label_width = 17 * len(label) + 16
            x = min(right - label_width - 7, anchor_x + 16)
            y = min(top - 29, anchor_y + 10)
            p.draw_line(anchor_x, anchor_y, x, y + 4, *landmark_color)
            rectangle(x, y, label_width, 24, panel)
            rectangle(x, y, label_width, 24, border, filled=False)
            self.font.draw(x + 8, y + 12, label, landmark_color)

        for position, color in ((world.pickup, ORANGE), (world.destination, TEAL)):
            x, y = map_point(*position)
            rectangle(x - 6, y - 6, 12, 12, ink)
            rectangle(x - 4, y - 4, 8, 8, color)
        destination_label = world.contract.name
        label_width = 17 * len(destination_label) + 16
        x, y = map_point(*world.destination)
        label_x = max(left + 4, x - label_width - 10)
        label_y = max(bottom + 4, y - 32)
        rectangle(label_x, label_y, label_width, 24, panel)
        self.font.draw(label_x + 8, label_y + 12, destination_label, TEAL)
        heading(*map_point(player.x, player.y), player.aim_angle)

        compass_x, compass_y = left + 28, top - 36
        self.font.draw(compass_x - 4, compass_y + 18, "N", WHITE)
        p.draw_line(compass_x, compass_y - 10, compass_x, compass_y + 8, *WHITE)
        p.draw_line(compass_x - 4, compass_y + 2, compass_x, compass_y + 8, *WHITE)
        p.draw_line(compass_x + 4, compass_y + 2, compass_x, compass_y + 8, *WHITE)
        rectangle(left, bottom, right - left, top - bottom, border, filled=False)
        self.font.draw(64, 674, "배달 구역 지도", WHITE)

        side = 880
        rectangle(side, 104, 336, 528, panel)
        rectangle(side, 104, 336, 528, border, filled=False)
        self.font.draw(side + 24, 602, "다음 목표", WHITE)
        waiting = world.parcel == "waiting"
        objective, target, accent = (
            ("택배 수령", "주황색 수령지에서 E", ORANGE) if waiting
            else ("택배 전달", "청록색 배송지에서 E", TEAL)
        )
        self.font.draw(side + 24, 566, objective, accent)
        self.font.draw(side + 24, 532, target, WHITE)
        p.draw_line(side + 24, 504, side + 312, 504, *border)
        self.font.draw(side + 24, 474, "지도 범례", WHITE)
        for y, label, color, w, h in (
            (432, "큰길", main_color, 24, 9),
            (394, "골목", alley_color, 24, 5),
            (356, "건물", building_color, 18, 14),
            (318, "상점·정류장", landmark_color, 18, 14),
            (242, "수령지", ORANGE, 8, 8),
            (204, "배송지", TEAL, 8, 8),
            (166, "폐차", wreck_color, 18, 8),
        ):
            rectangle(side + 36 - w / 2, y - h / 2, w, h, color)
            self.font.draw(side + 62, y, label, WHITE)
        heading(side + 31, 280, 0)
        self.font.draw(side + 62, 280, "현재 위치·방향", WHITE)
        rectangle(64, 40, 29, 27, panel)
        rectangle(64, 40, 29, 27, border, filled=False)
        self.font.draw(73, 54, "M", WHITE)
        self.font.draw(105, 54, "닫기 · 지도 확인 중 일시정지", WHITE)

    def draw_ground_light(self, light, outline, edge, falloff):
        points = [light.origin] + [point for point, _ in outline]
        ground = self.neighborhood_ground
        world_w, world_h = light.world_size
        vertices = (p.SDL_Vertex * len(points))()
        for i, point in enumerate(points):
            x, y = self.project(*point)
            strength = max(0, 1.0 - math.dist(light.origin, point) / light.radius)
            light_rgb = tuple(base + gain * strength for base, gain in zip(edge, falloff))
            uv = p.SDL_FPoint()
            if ground is not None:
                light_rgb = tuple(channel * 255 / GROUND_NEUTRAL for channel in light_rgb)
                uv = p.SDL_FPoint(max(0, min(1, point[0] / world_w)), max(0, min(1, 1 - point[1] / world_h)))
            color = p.SDL_Color(*(round(channel) for channel in light_rgb), 255)
            vertices[i] = p.SDL_Vertex(p.SDL_FPoint(x, WINDOW_HEIGHT - 1 - y), color, uv)
        indices = [index for i in range(1, len(vertices) - 1) for index in (0, i, i + 1)]
        triangles = (ctypes.c_int * len(indices))(*indices)
        texture = ground.texture if ground is not None else None
        if p.SDL_RenderGeometry(p.renderer, texture, vertices, len(vertices), triangles, len(indices)) != 0:
            raise RuntimeError(f"Ground light geometry failed: {p.SDL_GetError()!r}")

    def draw_streetlight_pools(self, lamps, outlines):
        if not lamps:
            return
        texture = self.neighborhood_ground.texture
        if p.SDL_SetTextureBlendMode(texture, p.SDL_BLENDMODE_ADD) != 0:
            raise RuntimeError(f"Streetlight blend mode failed: {p.SDL_GetError()!r}")
        try:
            for lamp, outline in zip(lamps, outlines):
                self.draw_ground_light(lamp, outline, (0, 0, 0), (108, 83, 48))
        finally:
            p.SDL_SetTextureBlendMode(texture, p.SDL_BLENDMODE_BLEND)

    def wall(self, wall, outlines, beam_mask=None):
        x, y = self.project(wall.x, wall.y)
        height = wall_height(wall)
        depth = wall.depth * GROUND_SCALE_Y
        if x >= WINDOW_WIDTH or x + wall.width <= 0 or y >= WINDOW_HEIGHT or y + height + depth <= 0:
            return

        textured = isinstance(wall, NeighborhoodWall)
        image = self.neighborhood_walls.get(wall.texture) if textured else None
        oblique = image is not None and wall.oblique
        if oblique:
            front, side, roof = house_planes(wall, x, y)
            foundation = quad(x, y, wall.width, depth + HOUSE_FOUNDATION_HEIGHT)
            for plane in (foundation, front, side, roof):
                self.draw_wall_plane(None, plane, 0, 1, (0, 0, 0))
        else:
            front = quad(x, y, wall.width, height)
            roof = quad(x, y + height, wall.width, depth)
            self.draw_wall_plane(None, quad(x, y, wall.width, height + depth), 0, 1, (0, 0, 0))

        seam = (image.h - round(height / 2)) / image.h if image is not None else 0.5
        front_band = min(1, ROOF_LIGHT_BAND / depth)
        side_band = min(1, ROOF_LIGHT_BAND / (front[1][0] - front[0][0]))
        facade_shade = (178, 147, 105) if image is not None else (53, 47, 40)
        low_obstacle = textured and wall.texture in ("parked-car", "abandoned-car", "dumpster")
        roof_shade = (140, 123, 102) if image is not None else (45, 41, 38)
        for axis, boundary, offset, length, edge in (
            (1, wall.y, wall.x, wall.width, "front"),
            (1, wall.y + wall.depth, wall.x, wall.width, "back"),
            (0, wall.x, wall.y, wall.depth, "left"),
            (0, wall.x + wall.width, wall.y, wall.depth, "right"),
        ):
            for index, outline in enumerate(outlines):
                mask = beam_mask if index == 0 else None
                for low, high in wall_edge_spans(wall, outline, axis, boundary):
                    start = max(0, (low - offset) / length)
                    end = min(1, (high - offset) / length)
                    if start >= end:
                        continue
                    if edge == "front":
                        self.draw_wall_plane(image, front, seam, 1, facade_shade, (start, 0, end, 1), mask=mask)
                        roof_bounds = (start, 0, end, front_band)
                        roof_alpha = (255, 255, 0, 0)
                    elif edge == "back":
                        roof_bounds = (start, 1 - front_band, end, 1)
                        roof_alpha = (0, 0, 255, 255)
                    elif edge == "left":
                        roof_bounds = (0, start, side_band, end)
                        roof_alpha = (255, 0, 0, 255)
                    else:
                        roof_bounds = (1 - side_band, start, 1, end)
                        roof_alpha = (0, 255, 255, 0)
                        if oblique:
                            side_image = self.neighborhood_walls[f"{wall.texture}-side"]
                            self.draw_wall_plane(side_image, side, 0, 1, (155, 131, 103), (start, 0, end, 1), mask=mask)
                    if low_obstacle and edge in ("left", "right"):
                        # Show the end of a low obstacle when approached along the lane.
                        band = side_band * min(1, (end - start) * 2)
                        bounds = (0, 0, band, 1) if edge == "left" else (1 - band, 0, 1, 1)
                        self.draw_wall_plane(image, front, seam, 1, facade_shade, bounds, mask=mask)
                    self.draw_wall_plane(image, roof, 0, seam, roof_shade, roof_bounds, alpha=roof_alpha, mask=mask)

    def draw_wall_plane(self, image, points, top, bottom, shade, bounds=(0, 0, 1, 1), *,
                        alpha=(255, 255, 255, 255), mask=None):
        left, near, right, far = bounds
        a, b, c, d = points
        coords = (clip_wall_plane(points, bounds, mask) if mask is not None else
                  ((left, near), (right, near), (right, far), (left, far)))
        if len(coords) < 3:
            return
        vertices = (p.SDL_Vertex * len(coords))()
        for i, (u, v) in enumerate(coords):
            # Crop in surface coordinates so diagonal edges and texture pixels stay aligned.
            u, v = max(left, min(right, u)), max(near, min(far, v))
            x, y = ((1 - v) * (a[axis] + u * (b[axis] - a[axis]))
                    + v * (d[axis] + u * (c[axis] - d[axis])) for axis in (0, 1))
            s, t = (u - left) / (right - left), (v - near) / (far - near)
            opacity = round((1 - t) * ((1 - s) * alpha[0] + s * alpha[1])
                            + t * (s * alpha[2] + (1 - s) * alpha[3]))
            vertices[i] = p.SDL_Vertex(p.SDL_FPoint(x, WINDOW_HEIGHT - y), p.SDL_Color(*shade, opacity),
                                       p.SDL_FPoint(u, bottom + v * (top - bottom)))
        indices = [index for i in range(1, len(coords) - 1) for index in (0, i, i + 1)]
        triangles = (ctypes.c_int * len(indices))(*indices)
        texture = image.texture if image is not None else None
        if p.SDL_RenderGeometry(p.renderer, texture, vertices, len(vertices), triangles, len(indices)) != 0:
            raise RuntimeError(f"Wall geometry failed: {p.SDL_GetError()!r}")

    def update_sprint_pulse(self, dt, position=None):
        if position is not None:
            self.sprint_pulse = position
            self.sprint_pulse_remaining = SPRINT_PULSE_DURATION
        else:
            self.sprint_pulse_remaining = max(0.0, self.sprint_pulse_remaining - dt)

    def draw_sprint_pulse(self):
        if self.sprint_pulse_remaining <= 0:
            return
        progress = 1.0 - self.sprint_pulse_remaining / SPRINT_PULSE_DURATION
        radius = 18 + progress * 32
        x, y = self.sprint_pulse
        points = [(x + radius * dx, y + radius * dy) for dx, dy in PULSE_RING]
        color = tuple(round(bright + (floor - bright) * progress)
                      for bright, floor in zip(TEAL, (48, 41, 34)))
        visible = [self.light.contains(point) for point in points]
        for index, (start, end) in enumerate(zip(points, points[1:])):
            if visible[index] and visible[index + 1]:
                p.draw_line(*self.project(*start), *self.project(*end), *color)

    def draw_lit_region(self, bounds, draw):
        left, bottom, width, height = bounds
        right = min(WINDOW_WIDTH, math.ceil(left + width))
        left = max(0, math.floor(left))
        top = max(0, math.floor(WINDOW_HEIGHT - bottom - height - 1))
        end = min(WINDOW_HEIGHT, math.ceil(WINDOW_HEIGHT - bottom))
        if left >= right or top >= end:
            return
        clipped = False
        previous, first = (), top
        try:
            for row in range(top, end + 1):
                spans = tuple((max(left, a), min(right, b)) for a, b in self.light_rows[row]
                              if a < right and b > left) if row < end else ()
                if spans == previous:
                    continue
                for start, stop in previous:
                    clip = p.SDL_Rect(start, first, stop - start, row - first)
                    p.SDL_RenderSetClipRect(p.renderer, ctypes.byref(clip))
                    clipped = True
                    draw()
                previous, first = spans, row
        finally:
            if clipped:
                p.SDL_RenderSetClipRect(p.renderer, None)

    def draw_lit_prop(self, position, image):
        x, y = self.project(*position)
        width, height = image.w * 2, image.h * 2
        self.draw_lit_region((x - image.w, y, width, height), lambda: image.draw(x, y + image.h, width, height))

    def draw_station(self, position, pickup):
        x, y = self.project(*position)

        def draw_box():
            if pickup:
                rectangle(x - 14, y, 28, 23, (138, 86, 47))
                rectangle(x - 14, y + 23, 28, 8, (186, 132, 76))
                rectangle(x - 3, y + 11, 6, 20, (226, 185, 106))
            else:
                rectangle(x - 17, y, 34, 43, (37, 100, 96))
                rectangle(x - 17, y + 43, 34, 5, (86, 155, 145))
                rectangle(x - 11, y + 25, 22, 5, (11, 29, 34))

        half_width = 14 if pickup else 17
        self.draw_lit_region((x - half_width, y, half_width * 2 + 1, 32 if pickup else 49), draw_box)
        if self.light.contains(position):
            rectangle(x + 19, y + 26, 50, 23, (16, 24, 28))
            self.font.draw(x + 26, y + 37, "수령" if pickup else "배달", ORANGE if pickup else TEAL)

    def draw_delivery_hud(self):
        delivery = self.delivery
        status, guide = {
            "waiting": ("미수령 · 0/1", "남서쪽 거점에서 택배 수령"),
            "carrying": ("소지 중 · 0/1", "M 지도에서 배송지 확인"),
            "delivered": ("전달 완료 · 1/1", ""),
        }[delivery.parcel]
        self.font.draw(24, 564, f"택배 {status}  |  {delivery.contract.name}", WHITE)
        if delivery.result != "playing":
            success = delivery.result == "delivered"
            title = "배달 성공" if success else "배달 실패 · 체력 소진"
            rectangle(425, 303, 430, 112, (17, 25, 31))
            rectangle(425, 303, 430, 112, TEAL if success else ORANGE, filled=False)
            self.font.draw(455, 382, title, TEAL if success else ORANGE)
            self.font.draw(455, 335, "R 배달 선택 · Esc 종료", WHITE)
        elif delivery.can_interact() and self.light.contains(delivery.next_stop):
            action = "택배 수령" if delivery.parcel == "waiting" else "택배 전달"
            self.font.draw(520, 56, f"E  {action}", TEAL)
        else:
            self.font.draw(24, 538, guide, WHITE)

    def draw_lit_zombie(self, zombie, combat, attack):
        x, y = self.project(zombie.x, zombie.y)
        bounds = self.combat_visual.zombie_rect(zombie, x, y)
        self.draw_lit_region(bounds, lambda: self.combat_visual.draw_zombie(zombie, x, y))
        self.draw_zombie_markers(zombie, combat, attack, x, y)

    def draw_zombie_markers(self, zombie, combat, attack, x, y):
        scale = self.combat_visual.display_scale
        if combat.result == "playing" and zombie.alive and zombie.state in ZOMBIE_MARKS:
            symbol, color = ZOMBIE_MARKS[zombie.state]
            left, bottom = x + 24 * scale, y + 96 * scale

            def draw_status():
                rectangle(left, bottom, 18, 18, (16, 24, 28))
                self.font.draw(left + 4, bottom + 9, symbol, color)

            self.draw_lit_region((left, bottom - 2, 19, 23), draw_status)
        if (attack is not None and attack.facing == "front_right"
                and attack.elapsed < attack.hit_time + HIT_MARK_DURATION
                and any(target is zombie for target in attack.hit_targets)):
            x, y = x - 12 * scale, y + 83 * scale

            def draw_hit():
                p.draw_line(x - 9, y + 4, x - 3, y + 1, *WHITE)
                p.draw_line(x - 2, y + 9, x, y + 3, *ORANGE)
                p.draw_line(x + 4, y + 4, x + 9, y + 2, *WHITE)

            self.draw_lit_region((x - 9, y, 20, 10), draw_hit)

    def draw(self, player, walls, target, focused=True):
        if self.choosing_delivery:
            self.draw_delivery_selection()
            return
        if self.map_open:
            self.draw_map(player)
            return
        p.SDL_SetRenderDrawColor(p.renderer, 0, 0, 0, 255)
        p.SDL_RenderClear(p.renderer)
        origin = (player.x, player.y)
        aim = sdl_to_world(*self.cursor, self.camera) if self.cursor is not None else target
        dx, dy = aim[0] - origin[0], aim[1] - origin[1]
        world_size = self.combat.world_size if self.combat is not None else (WORLD_WIDTH, WORLD_HEIGHT)
        beam = Flashlight(origin, math.atan2(dy, dx) if dx or dy else player.aim_angle, walls, world_size)
        lamps = tuple(self.streetlights_in_view())
        self.light = LightField((beam, *lamps))
        self.light_rows = light_screen_rows(self.light.lights, self.project)
        beam_outline = beam.outline()
        # The ground cone ends at a wall's foot. Use the beam's shape before that collision
        # to clip the visible face, while the hit outline still selects which face gets light.
        open_beam = Flashlight(origin, beam.angle, (), world_size)
        beam_mask = []
        for point in (origin, *(point for point, _ in open_beam.outline())):
            x, y = self.project(*point)
            beam_mask.append((x, y + 1))
        lamp_outlines = tuple(lamp.outline() for lamp in lamps)
        self.draw_ground_light(beam, beam_outline, (28, 26, 23), (104, 84, 53))
        self.draw_streetlight_pools(lamps, lamp_outlines)
        outlines = (beam_outline, *lamp_outlines)
        self.draw_sprint_pulse()
        foot = self.project(*origin)
        combat = getattr(self, "combat", None)
        attack = combat.attack if combat is not None else None
        delivery = self.delivery
        courier_style = {"empty_handed": delivery.parcel != "carrying"} if delivery is not None else {}
        for kind, actor in sorted_drawables(player, walls, zombies=combat.zombies if combat else (),
                                            prop=TRASH_CAN_POSITION if delivery is None else None,
                                            station=delivery.next_stop if delivery is not None else None,
                                            lamps=(lamp.origin for lamp in lamps),
                                            street_props=delivery.props if delivery is not None else ()):
            if kind == "prop":
                self.draw_lit_prop(actor, self.trash_can)
            elif kind == "street-prop":
                self.draw_lit_prop((actor.x, actor.y), self.street_prop_images[actor.texture])
            elif kind == "station":
                self.draw_station(actor, delivery.parcel == "waiting")
            elif kind == "lamp":
                self.draw_lit_prop(actor, self.streetlamp_image)
            elif kind == "wall":
                self.wall(actor, outlines, beam_mask)
            elif kind == "zombie":
                self.draw_lit_zombie(actor, combat, attack)
            else:
                if combat is None or not self.combat_visual.draw_attack(
                        combat.attack, *foot, walk_frame_index=self.player_visual.frame_index, **courier_style):
                    self.player_visual.draw(*foot, **courier_style)
                cross(*foot, TEAL, size=4)
        # The cursor stays at its screen position while the world shakes.
        target_screen = (world_to_screen(*target, self.camera) if self.cursor is None
                         else (self.cursor[0], WINDOW_HEIGHT - 1 - self.cursor[1]))
        cross(*target_screen, ORANGE, size=7)
        angle = attack.angle if attack is not None else player.aim_angle
        desired = math.atan2(target[1] - player.y, target[0] - player.x)
        if abs(math.remainder(desired - angle, math.tau)) > math.radians(5):
            tip = self.project(player.x + 27 * math.cos(angle), player.y + 27 * math.sin(angle))
            p.draw_line(*foot, *tip, *TEAL)
            cross(*tip, TEAL, size=2)
        title = "Dead Route  |  골목 배달" if delivery is not None else "Dead Route  |  전투 검수"
        controls = "WASD 이동 · Shift 달리기 · 마우스 조준 · 좌클릭 공격"
        if delivery is not None:
            controls += " · E 수령/전달 · M 지도 · R 배달 선택"
        else:
            controls += " · R 재시작"
        self.font.draw(24, 683, title, WHITE)
        self.font.draw(24, 651, controls + " · Esc 종료", WHITE)
        if combat is not None:
            self.font.draw(24, 620, f"HP {combat.player_hp}/3", WHITE)
            self.font.draw(24, 592, "스태미나", WHITE)
            rectangle(116, 585, 100, 10, (48, 63, 71))
            stamina_width = round(100 * combat.stamina / MAX_STAMINA)
            if stamina_width:
                rectangle(116, 585, stamina_width, 10, TEAL)
            if delivery is not None:
                self.draw_delivery_hud()
            elif combat.result != "playing":
                message = "연습 좀비 처치" if combat.result == "cleared" else "쓰러짐"
                self.font.draw(470, 365, f"{message} · R 재시작", TEAL)
        self.font.draw(24, 54, "입력 활성" if focused else "포커스 없음 · 이동 입력 초기화", WHITE)


def capture(path):
    """Save actual SDL back-buffer pixels before Present."""
    path.parent.mkdir(parents=True, exist_ok=True)
    surface = p.SDL_CreateRGBSurfaceWithFormat(
        0, WINDOW_WIDTH, WINDOW_HEIGHT, 32, p.SDL_PIXELFORMAT_ARGB8888)
    if not surface:
        raise RuntimeError(f"SDL capture allocation failed: {p.SDL_GetError()!r}")
    try:
        if p.SDL_RenderReadPixels(p.renderer, None, p.SDL_PIXELFORMAT_ARGB8888,
                                 surface.contents.pixels, surface.contents.pitch) != 0:
            raise RuntimeError(f"SDL capture failed: {p.SDL_GetError()!r}")
        if p.IMG_SavePNG(surface, str(path).encode("utf-8")) != 0:
            raise RuntimeError(f"PNG save failed: {path}")
    finally:
        p.SDL_FreeSurface(surface)


def poll_events():
    """Read raw events, retaining focus changes without FPS title updates."""
    while True:
        event = p.SDL_Event()
        if not p.SDL_PollEvent(ctypes.byref(event)):
            return
        yield event


def play_opening(renderer, music):
    start = previous = time.perf_counter()
    while True:
        now = time.perf_counter()
        skip = False
        lost_focus = False
        for event in poll_events():
            if event.type == p.SDL_QUIT:
                return False
            if event.type == p.SDL_KEYDOWN and not event.key.repeat:
                if event.key.keysym.sym == p.SDLK_ESCAPE:
                    return False
                if event.key.keysym.sym in (p.SDLK_RETURN, p.SDLK_KP_ENTER):
                    skip = True
            if (event.type == p.SDL_WINDOWEVENT
                    and event.window.event == p.SDL_WINDOWEVENT_FOCUS_LOST):
                lost_focus = True
        elapsed = now - start
        if skip or elapsed >= opening.DURATION:
            return True
        focused = bool(p.SDL_GetWindowFlags(p.window) & p.SDL_WINDOW_INPUT_FOCUS)
        music.update(min(now - previous, 0.05), opening=True, focused=focused and not lost_focus)
        opening.draw(elapsed, renderer.font, renderer.player_visual, renderer.combat_visual.metadata["zombie"])
        p.update_canvas()
        previous = now


def run(smoke_test=False, *, show_opening=False, practice=False):
    renderer = None
    music = None
    zombie_audio = None
    delivery_run = not (smoke_test or practice)
    try:
        p.open_canvas(WINDOW_WIDTH, WINDOW_HEIGHT, sync=True)
        if not p.renderer:
            p.renderer = p.SDL_CreateRenderer(p.window, -1, p.SDL_RENDERER_SOFTWARE)
        if not p.renderer:
            raise RuntimeError(f"SDL renderer initialization failed: {p.SDL_GetError()!r}")
        p.hide_lattice()
        p.SDL_SetWindowTitle(p.window, b"Dead Route" if delivery_run else b"Dead Route - R2-ZA")
        p.SDL_SetWindowPosition(p.window, p.SDL_WINDOWPOS_CENTERED, p.SDL_WINDOWPOS_CENTERED)
        p.SDL_SetRenderDrawBlendMode(p.renderer, p.SDL_BLENDMODE_BLEND)
        renderer = Renderer()
        if show_opening and not smoke_test:
            from spatial_audio import BackgroundMusic

            music = BackgroundMusic(BASE_DIR / "assets/audio/last-delivery.mp3")
            music.start()
            if not play_opening(renderer, music):
                return
        if not smoke_test:
            zombie_audio = ZombieAudio(BASE_DIR / "assets/audio")
        world = DeliveryWorld() if delivery_run else CombatWorld()
        renderer.combat = world
        if delivery_run:
            renderer.delivery = world
            renderer.choosing_delivery = True
            renderer.player_visual.display_scale = DELIVERY_CHARACTER_SCALE
            renderer.combat_visual.display_scale = DELIVERY_CHARACTER_SCALE
            renderer.player_visual.load_delivery_sprites()
            renderer.combat_visual.load_empty_hands()
            renderer.load_neighborhood()
        player, walls = world.player, world.walls
        pressed = set()
        target = world.pickup if delivery_run else (world.zombie.x, world.zombie.y)
        aim_player(player, *target)
        cursor = current_cursor()
        mouse_held = False
        previous = time.perf_counter()
        frame = 0
        running = True
        smoke_poses = (("initial", 480, 180), ("wall-behind", 480, 420),
                       ("wall-front", 480, 300))
        while running:
            now = time.perf_counter()
            dt = min(now - previous, 0.05)
            previous = now
            pending_click = False
            pending_interact = False
            contract_choice = None
            reset_requested = False
            lost_focus = False
            map_toggle = False
            for event in poll_events():
                if event.type == p.SDL_QUIT:
                    running = False
                elif event.type == p.SDL_KEYDOWN and not event.key.repeat:
                    key = event.key.keysym.sym
                    if key == p.SDLK_ESCAPE:
                        running = False
                        continue
                    if renderer.choosing_delivery:
                        if contract_choice is None:
                            contract_choice = DELIVERY_KEYS.get(key)
                        continue
                    if key == p.SDLK_e and key not in pressed:
                        pending_interact = True
                    elif key == p.SDLK_m and key not in pressed:
                        map_toggle = not map_toggle
                    pressed.add(key)
                    if key == p.SDLK_r:
                        reset_requested = True
                elif event.type == p.SDL_KEYUP and not event.key.repeat:
                    pressed.discard(event.key.keysym.sym)
                elif event.type == p.SDL_MOUSEMOTION:
                    cursor = (event.motion.x, event.motion.y)
                elif event.type == p.SDL_MOUSEBUTTONDOWN and event.button.button == p.SDL_BUTTON_LEFT:
                    cursor = (event.button.x, event.button.y)
                    if not renderer.choosing_delivery and not mouse_held:
                        pending_click = True
                    mouse_held = True
                elif event.type == p.SDL_MOUSEBUTTONUP and event.button.button == p.SDL_BUTTON_LEFT:
                    mouse_held = False
                elif (event.type == p.SDL_WINDOWEVENT
                      and event.window.event == p.SDL_WINDOWEVENT_FOCUS_LOST):
                    pressed.clear()
                    pending_click = False
                    pending_interact = False
                    mouse_held = False
                    lost_focus = True
            if not running:
                break
            focused = bool(p.SDL_GetWindowFlags(p.window) & p.SDL_WINDOW_INPUT_FOCUS)
            if not focused:
                pressed.clear()
                pending_click = False
                pending_interact = False
                mouse_held = False
            if not focused or lost_focus:
                contract_choice = None
            if reset_requested or contract_choice is not None:
                if contract_choice is not None:
                    world.select_contract(contract_choice)
                else:
                    world.reset()
                renderer.choosing_delivery = delivery_run and reset_requested
                if delivery_run:
                    renderer.reset_streetlights()
                player, walls = world.player, world.walls
                renderer.player_visual.locomotion = Locomotion()
                renderer.combat_visual.reset_zombie_animation()
                pressed.clear()
                pending_click = False
                pending_interact = False
                mouse_held = False
                cursor = current_cursor()
                renderer.light = None
                renderer.map_open = False
                renderer.update_shake(math.inf)
                renderer.update_sprint_pulse(math.inf)
                target = world.pickup if delivery_run else (world.zombie.x, world.zombie.y)
                aim_player(player, *target)
            elif map_toggle and focused and not lost_focus and delivery_run and world.result == "playing":
                renderer.map_open = not renderer.map_open
                pressed.clear()
                pending_click = pending_interact = mouse_held = False
            if renderer.choosing_delivery:
                if music is not None:
                    music.update(dt, focused=False)
                if zombie_audio is not None:
                    zombie_audio.update(dt, distance=None, stride=0.0, active=False)
                renderer.draw(player, walls, target, focused)
                p.update_canvas()
                continue
            renderer.follow(player)
            renderer.cursor = cursor
            if cursor is not None:
                light = renderer.light
                if light is None:
                    beam = Flashlight((player.x, player.y), player.aim_angle, walls, world.world_size)
                    light = LightField((beam, *renderer.streetlights_in_view()))
                target = mouse_target(world, renderer.combat_visual, *cursor, light, renderer.camera, renderer.shake_offset)
            active = focused and not lost_focus and not renderer.map_open and contract_choice is None
            axis_x = int(p.SDLK_d in pressed) - int(p.SDLK_a in pressed)
            axis_y = int(p.SDLK_w in pressed) - int(p.SDLK_s in pressed)
            motion = renderer.player_visual.locomotion
            facing_hint = motion.facing if motion._initialized else None
            if pending_click and active:
                facing = select_facing(player.aim_angle, facing_hint)
                world.start_attack(facing=facing, stationary_front_right=True)
            before = (player.x, player.y)
            zombie_origins = [(zombie.x, zombie.y) for zombie in world.zombies]
            strike = world.attack
            was_landed = strike is not None and strike.landed
            hp_before = world.player_hp
            sprint = p.SDLK_LSHIFT in pressed or p.SDLK_RSHIFT in pressed
            world.update(dt if active else 0.0, axis_x, axis_y, facing_hint=facing_hint, sprint=sprint)
            if delivery_run and active and pending_interact:
                world.interact()
            if active and not reset_requested and world.result == "playing":
                renderer.update_sprint_pulse(dt, world.sprint_step)
            else:
                renderer.update_sprint_pulse(math.inf)
            strength = 0
            if world.player_hp < hp_before:
                strength = 4
            elif strike is not None and strike.landed and not was_landed:
                strength = 3
            renderer.update_shake(dt if active and not reset_requested else math.inf, strength)
            distance = None
            nearest_zombie = None
            stride = 0.0
            for zombie, (x, y) in zip(world.zombies, zombie_origins):
                zombie_dx, zombie_dy = zombie.x - x, zombie.y - y
                renderer.combat_visual.update_zombie(zombie, zombie_dx, zombie_dy, paused=not active)
                if zombie.alive:
                    enemy_distance = math.hypot(zombie.x - player.x, zombie.y - player.y)
                    if distance is None or enemy_distance < distance:
                        distance = enemy_distance
                        nearest_zombie = zombie
                        recoil_x, recoil_y = zombie.recoil_offset
                        stride = math.hypot(zombie_dx - recoil_x, zombie_dy - recoil_y)
            if music is not None:
                music.update(dt, distance=distance, focused=active)
            if zombie_audio is not None:
                hearing_active = active and not reset_requested and world.result == "playing"
                occluded = hearing_active and nearest_zombie is not None and any(
                    wall_blocks((player.x, player.y), (nearest_zombie.x, nearest_zombie.y), wall)
                    for wall in walls)
                zombie_audio.update(dt, distance=distance, stride=stride, active=hearing_active,
                                    occluded=occluded)
            dx, dy = player.x - before[0], player.y - before[1]
            if smoke_test:
                name, player.x, player.y = smoke_poses[frame]
            previous_camera = renderer.camera
            renderer.follow(player)
            if cursor is not None and renderer.camera != previous_camera:
                target = mouse_target(world, renderer.combat_visual, *cursor, light, renderer.camera, renderer.shake_offset)
            if active and strike is None and world.result == "playing":
                aim_player(player, *target, max_turn=TURN_SPEED * dt)
            display_angle = world.attack.angle if world.attack is not None else player.aim_angle
            renderer.player_visual.update(display_angle, dx, dy, sprinting=delivery_run and world.sprinting)
            renderer.draw(player, walls, target, focused)
            if smoke_test:
                output = BASE_DIR.parent / "output/review/R2-C8" / f"ui-{name}.png"
                capture(output)
                print(f"R2-C8 SDL capture: {output}", flush=True)
            p.update_canvas()
            if smoke_test:
                frame += 1
                if frame >= len(smoke_poses):
                    running = False
    finally:
        try:
            if zombie_audio is not None:
                zombie_audio.close()
        finally:
            try:
                if music is not None:
                    music.close()
            finally:
                try:
                    if renderer is not None:
                        renderer.close()
                finally:
                    p.close_canvas()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dead Route alley delivery game")
    parser.add_argument("--smoke-test", action="store_true",
                        help="render three native SDL fixtures, save PNGs and exit")
    args = parser.parse_args()
    run(args.smoke_test, show_opening=not args.smoke_test)
