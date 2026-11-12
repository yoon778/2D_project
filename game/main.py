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
from delivery_progress import load_two_stop_unlock, save_two_stop_unlock
from flashlight import Flashlight, LightField, feathered_beam_mesh, nearby_glow
from locomotion import Locomotion, select_facing
from play_hud import PlayHUD
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
DELIVERY_KEYS = {p.SDLK_1: 0, p.SDLK_KP_1: 0, p.SDLK_2: 1, p.SDLK_KP_2: 1, p.SDLK_3: 2, p.SDLK_KP_3: 2}
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
    "iron-gate": [25, 23],
    "shop": [130, 103],
    "bus-stop": [70, 50],
    "parked-car": [56, 31],
    "abandoned-car": [56, 31],
    "dumpster": [30, 24],
}
LOW_OBSTACLE_TEXTURES = ("parked-car", "abandoned-car", "dumpster")
BUILDING_TEXTURES = {"west-house", "east-house", "shop", "workshop"}
PROP_TEXTURE_SIZES = {
    "mailbox": [10, 24],
    "planter": [13, 15],
    "bicycle": [23, 16],
    "trash-bags": [15, 12],
    "metal-bin": [13, 21],
    "recycling-bin": [14, 22],
    "empty-bottle": [8, 11],
}
HOUSE_FOUNDATION_HEIGHT = 8
ROOF_LIGHT_BAND = 24
GROUND_NEUTRAL = 144
STREETLIGHT_RADIUS = 185.0
NEARBY_GLOW_COLOR = (42, 38, 31)
NEARBY_GLOW_TINT = 66
ZOMBIE_LIGHT_DEPTH_SCALE = 0.35
TRASH_CAN_POSITION = (365.0, 300.0)
WHITE = (231, 236, 231)
TEAL = (86, 225, 194)
ORANGE = (255, 182, 78)
MAP_INK = (14, 20, 23)
MAP_PANEL = (27, 39, 41)
MAP_BORDER = (91, 112, 112)
MAP_ROAD = (170, 145, 106)
MAP_ALLEY = (99, 132, 130)
MAP_WRECK = (177, 101, 77)
MAP_CLOSED_GATE = (204, 150, 104)
MAP_OPEN_GATE = (122, 188, 153)
MAP_BUILDING = (20, 30, 34)
MAP_LANDMARK = (178, 201, 195)
MAP_COMPLETED = (161, 176, 166)
HIT_MARK_DURATION = 0.06
NOISE_PULSE_DURATION = 0.24
VEHICLE_ALARM_DURATION = 1.2
PULSE_RING = tuple((math.cos(i * math.tau / 24), math.sin(i * math.tau / 24)) for i in range(25))
ZOMBIE_MARKS = {"chase": ("!", ORANGE), "investigate": ("?", TEAL), "search": ("?", TEAL)}
SNEAK_HINT_RANGE = 160.0
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


def sorted_drawables(player, walls, zombie=None, *, zombies=(), prop=None, stations=(), lamps=(), street_props=(),
                     bottles=()):
    # Stable ties: fixed props precede walls and characters at the same ground y.
    objects = [("prop", prop)] if prop is not None else []
    objects.extend(("station", position) for position in stations)
    objects.extend(("lamp", position) for position in lamps)
    objects.extend(("street-prop", decoration) for decoration in street_props)
    objects.extend(("bottle", bottle) for bottle in bottles)
    objects.extend(("wall", wall) for wall in walls)
    if zombie is not None:
        objects.append(("zombie", zombie))
    objects.extend(("zombie", enemy) for enemy in zombies)
    objects.append(("player", player))
    return sorted(objects, key=lambda item: -(item[1][1] if item[0] in ("prop", "station", "lamp", "bottle")
                                               else item[1].y))


def merge_light_spans(spans):
    merged = []
    for left, right in sorted(spans):
        if merged and left <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], right))
        else:
            merged.append((left, right))
    return merged


def light_source_rows(light, project):
    """Rasterize a single projected outline so its wall shadow stays with its light."""
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
    rows = {}
    for row, edges in crossings.items():
        edges.sort()
        rows[row] = tuple((left, right) for left, right in zip(edges[::2], edges[1::2]) if left < right)
    return rows


def combined_light_rows(sources):
    return [merge_light_spans(span for rows in sources for span in rows.get(row, ()))
            for row in range(WINDOW_HEIGHT)]


def dim_color(color):
    return tuple(round(channel * NEARBY_GLOW_TINT / 255) for channel in color)


def draw_dimmed_texture(texture, draw):
    tint = NEARBY_GLOW_TINT
    if p.SDL_SetTextureColorMod(texture, tint, tint, tint) != 0:
        raise RuntimeError(f"Nearby light tint failed: {p.SDL_GetError()!r}")
    try:
        draw()
    finally:
        p.SDL_SetTextureColorMod(texture, 255, 255, 255)


def zombie_light_row(row, foot_y):
    # A standing sprite's height only partially contributes to its ground depth.
    foot_row = WINDOW_HEIGHT - 1 - foot_y
    return math.floor(foot_row + (row + .5 - foot_row) * ZOMBIE_LIGHT_DEPTH_SCALE)


def light_depth_columns(light, ground_y, offset_x):
    return [(math.ceil(left + offset_x - .5), math.ceil(right + offset_x - .5))
            for left, right in light.spans_at(ground_y)]


def clip_light_columns(spans, columns):
    return [(max(left, start), min(right, stop)) for left, right in spans for start, stop in columns
            if left < stop and start < right]


def mouse_target(world, visual, mouse_x, mouse_y, light=None, camera=(0.0, 0.0), shake=(0, 0), *, wall_alpha=None):
    screen_y = WINDOW_HEIGHT - 1 - mouse_y
    for zombie in sorted(world.zombies, key=lambda enemy: enemy.y):
        position = (zombie.x, zombie.y)
        x, y = world_to_screen(*position, camera)
        if not visual.zombie_contains(zombie, x + shake[0], y + shake[1], mouse_x, screen_y):
            continue
        if light is not None:
            sample = zombie_light_row(mouse_y, y + shake[1])
            world_x, depth = screen_to_world(mouse_x + .5 - shake[0],
                                              WINDOW_HEIGHT - 1.5 - sample - shake[1], camera)
            if not any(any(left <= world_x < right for left, right in source.spans_at(zombie.y))
                       and any(left <= world_x < right for left, right in source.spans_at(depth))
                       for source in light.lights):
                continue
        # A wall drawn in front can cover the upper part of a lit sprite.
        wx, wy = mouse_x - shake[0], screen_y - shake[1]
        for wall in world.walls:
            if wall.y >= zombie.y or building_covers_player(wall, world.player, camera):
                continue
            left, bottom = world_to_screen(wall.x, wall.y, camera)
            alpha_rows = wall_alpha.get(wall.texture) if wall_alpha and isinstance(wall, NeighborhoodWall) else None
            if wall_covers(wall, left, bottom, wx, wy, alpha_rows):
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


def wall_covers(wall, left, bottom, x, y, alpha_rows=None):
    oblique = isinstance(wall, NeighborhoodWall) and wall.oblique
    if oblique or alpha_rows is not None:
        # SDL fills triangles at the pixel center.
        x, y = x + .5, y + .5
    height, depth = wall_height(wall), wall.depth * GROUND_SCALE_Y
    if not (left <= x < left + wall.width and bottom <= y < bottom + height + depth):
        return False
    if alpha_rows is not None:
        # Use the same front/roof split as the textured occlusion pass.
        rise = y - bottom
        front_rows = round(height / 2)
        if rise < height:
            row = len(alpha_rows) - rise * front_rows / height
        else:
            row = (len(alpha_rows) - front_rows) * (1 - (rise - height) / depth)
        column = int((x - left) * len(alpha_rows[0]) / wall.width)
        return bool(alpha_rows[min(len(alpha_rows) - 1, int(row))][column])
    if not oblique:
        return True
    if y < bottom + depth + HOUSE_FOUNDATION_HEIGHT:
        return True
    # The projected house planes are convex and ordered counterclockwise.
    return any(all((bx - ax) * (y - ay) >= (by - ay) * (x - ax)
                   for (ax, ay), (bx, by) in zip(plane, (*plane[1:], plane[0])))
               for plane in house_planes(wall, left, bottom))


def building_covers_player(wall, player, camera):
    if (not isinstance(wall, NeighborhoodWall) or wall.texture not in BUILDING_TEXTURES
            or player.y < wall.y + wall.depth):
        return False
    # The ground anchor keeps the cutaway stable across poses and held equipment.
    left, bottom = world_to_screen(wall.x, wall.y, camera)
    x, y = world_to_screen(player.x, player.y, camera)
    return wall_covers(wall, left, bottom, x, y)


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


def load_wall_alpha(path):
    source = p.IMG_Load(str(path).encode("utf-8"))
    if not source:
        raise OSError(f"Could not load wall alpha: {path}")
    try:
        surface = p.SDL_ConvertSurfaceFormat(source, p.SDL_PIXELFORMAT_RGBA32, 0)
    finally:
        p.SDL_FreeSurface(source)
    if not surface:
        raise RuntimeError(f"Could not convert wall alpha: {p.SDL_GetError()!r}")
    try:
        width, height, pitch = surface.contents.w, surface.contents.h, surface.contents.pitch
        pixels = ctypes.string_at(surface.contents.pixels, pitch * height)
        return tuple(pixels[row * pitch + 3:row * pitch + width * 4:4] for row in range(height))
    finally:
        p.SDL_FreeSurface(surface)


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
        self.play_hud = None
        self.player_visual = None
        self.combat_visual = None
        self.trash_can = None
        self.neighborhood_ground = None
        self.neighborhood_walls = {}
        self.wall_alpha = {}
        self.street_prop_images = {}
        self.streetlamp_image = None
        self.streetlights = ()
        self.combat = None
        self.delivery = None
        self.cursor = None
        self.light = None
        self.glow_source = None
        self.camera = (0.0, 0.0)
        self.choosing_delivery = False
        self.delivery_preview = 0
        self.map_open = False
        self.shake_remaining = 0.0
        self.shake_strength = 0
        self.shake_offset = (0, 0)
        self.sprint_pulse = None
        self.sprint_pulse_remaining = 0.0
        self.bottle_pulse = None
        self.bottle_pulse_remaining = 0.0
        self.vehicle_alarm = None
        self.vehicle_alarm_remaining = 0.0
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
        self.combat_visual.load_zombie_appearances()
        world_w, world_h = self.delivery.world_size
        self.neighborhood_ground = load_atlas(NEIGHBORHOOD_PATH / "ground.png",
                                              [round(world_w / 2), round(world_h * GROUND_SCALE_Y / 2)])
        if p.SDL_SetTextureBlendMode(self.neighborhood_ground.texture, p.SDL_BLENDMODE_BLEND) != 0:
            raise RuntimeError(f"Ground blend mode failed: {p.SDL_GetError()!r}")
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
        self.wall_alpha = {key: load_wall_alpha(NEIGHBORHOOD_PATH / f"{key}.png")
                           for key in LOW_OBSTACLE_TEXTURES if key in self.neighborhood_walls}
        self.street_prop_images = {
            key: load_atlas(NEIGHBORHOOD_PATH / f"{key}.png", size) for key, size in PROP_TEXTURE_SIZES.items()
        }
        self.streetlamp_image = load_atlas(NEIGHBORHOOD_PATH / "streetlamp.png", [14, 54])
        self.reset_streetlights()
        self.play_hud = PlayHUD(BASE_DIR / "assets/ui/NotoSansKR-Regular.ttf", WINDOW_WIDTH, WINDOW_HEIGHT)

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
        if self.play_hud is not None:
            self.play_hud.close()
            self.play_hud = None
        self.street_prop_images.clear()
        self.streetlamp_image = None
        self.neighborhood_ground = None
        self.neighborhood_walls.clear()
        self.wall_alpha.clear()
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
        world = self.delivery
        p.SDL_SetRenderDrawColor(p.renderer, *MAP_INK, 255)
        p.SDL_RenderClear(p.renderer)
        self.font.draw(64, 672, "DEAD ROUTE  |  배달 선택", TEAL)
        rectangle(64, 104, 378, 528, MAP_PANEL)
        rectangle(64, 104, 378, 528, MAP_BORDER, filled=False)
        for index, contract in enumerate(DELIVERY_CONTRACTS):
            bottom = 506 - index * 116
            selected = index == self.delivery_preview
            accent = TEAL if selected else MAP_BORDER
            rectangle(82, bottom, 342, 106, (38, 56, 56) if selected else (18, 29, 32))
            rectangle(82, bottom, 342, 106, accent, filled=False)
            if contract not in world.available_contracts:
                self.font.draw(100, bottom + 77, f"[{index + 1}]  {contract.name} · 잠금", MAP_LANDMARK)
                self.font.draw(100, bottom + 40, "기존 배달 1회 성공 후 해금", MAP_LANDMARK)
                continue
            self.font.draw(100, bottom + 77, f"[{index + 1}]  {contract.name}", TEAL if selected else WHITE)
            self.font.draw(100, bottom + 49, f"난이도 · {contract.difficulty}", ORANGE)
            self.font.draw(100, bottom + 22, contract.description, WHITE)
        keys = "1 / 2 / 3" if world.two_stop_unlocked else "1 / 2"
        self.font.draw(100, 213, f"{keys}  미리보기", WHITE)
        self.font.draw(100, 170, "Enter  배달 시작  ·  Esc  종료", TEAL)

        contract = DELIVERY_CONTRACTS[self.delivery_preview]
        self.font.draw(496, 610, f"{contract.name} 지도", WHITE)
        self.draw_town_map(contract, 496, 104, 720, 480)
        for x, color, label in ((496, ORANGE, "수령지"), (608, TEAL, "배송지")):
            rectangle(x, 65, 8, 8, color)
            self.font.draw(x + 16, 69, label, WHITE)
        if DELIVERY_CONTRACTS[1].stops[0] in contract.stops:
            rectangle(720, 67, 10, 4, MAP_CLOSED_GATE)
            self.font.draw(736, 69, "철문", WHITE)

    @staticmethod
    def draw_map_heading(x, y, angle):
        dx, dy = math.cos(angle), math.sin(angle)
        tip_x, tip_y = x + 16 * dx, y + 16 * dy
        p.draw_line(x, y, tip_x, tip_y, *WHITE)
        for side in (-1, 1):
            p.draw_line(tip_x, tip_y, tip_x - 6 * dx - 4 * dy * side,
                        tip_y - 6 * dy + 4 * dx * side, *WHITE)
        rectangle(x - 4, y - 4, 8, 8, MAP_INK)
        rectangle(x - 2, y - 2, 4, 4, WHITE)

    def draw_town_map(self, contract, x, y, viewport_width, viewport_height, player=None):
        world = self.delivery
        width, height = world.world_size
        scale = min(viewport_width / width, viewport_height / height)
        left = x + (viewport_width - width * scale) / 2
        bottom = y + (viewport_height - height * scale) / 2
        right = left + width * scale
        top = bottom + height * scale

        def map_point(x, y):
            return left + x * scale, bottom + y * scale

        rectangle(left, bottom, right - left, top - bottom, (41, 56, 57))
        for roads, color in ((TOWN_ROADS["alleys"], MAP_ALLEY),
                             (TOWN_ROADS["main"], MAP_ROAD),
                             ((TOWN_ROADS["main_detour"],), MAP_ALLEY)):
            for road in roads:
                points = road["points"]
                segments = [(a, b, road["width"]) for a, b in zip(points, points[1:])]
                segments.extend((point, point, road["width"] + 10) for point in road.get("junctions", ()))
                for (ax, ay), (bx, by), road_width in segments:
                    half_width = road_width / 2
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
            fill = MAP_WRECK if texture == "abandoned-car" else MAP_BUILDING
            rectangle(x, y, w, h, fill)
            rectangle(x, y, w, h, MAP_LANDMARK if label else MAP_BORDER, filled=False)
            if label:
                landmarks.append((label, x + w / 2, y + h))

        for label, anchor_x, anchor_y in landmarks:
            label_width = 17 * len(label) + 16
            x = min(right - label_width - 7, anchor_x + 16)
            y = min(top - 29, anchor_y + 10)
            p.draw_line(anchor_x, anchor_y, x, y + 4, *MAP_LANDMARK)
            rectangle(x, y, label_width, 24, MAP_PANEL)
            rectangle(x, y, label_width, 24, MAP_BORDER, filled=False)
            self.font.draw(x + 8, y + 12, label, MAP_LANDMARK)

        x, y = map_point(*world.pickup)
        rectangle(x - 6, y - 6, 12, 12, MAP_INK)
        rectangle(x - 4, y - 4, 8, 8, ORANGE)
        for stop in contract.stops:
            completed = player is not None and stop in world.completed_stops
            color = MAP_COMPLETED if completed else TEAL
            x, y = map_point(*stop.position)
            rectangle(x - 6, y - 6, 12, 12, MAP_INK)
            rectangle(x - 4, y - 4, 8, 8, color)
            label = stop.name
            if player is not None and len(contract.stops) > 1:
                label += " · 완료" if completed else " · 미완료"
            label_width = 17 * len(label) + 16
            label_x = max(left + 4, x - label_width - 10)
            label_y = max(bottom + 4, y - 32)
            rectangle(label_x, label_y, label_width, 24, MAP_PANEL)
            self.font.draw(label_x + 8, label_y + 12, label, color)
        if DELIVERY_CONTRACTS[1].stops[0] in contract.stops:
            gate_x, gate_y = map_point(*world.gate_position)
            gate_closed = player is None or world.gate is not None
            rectangle(gate_x - 5, gate_y - 7, 10, 4, MAP_INK)
            rectangle(gate_x - 4, gate_y - 6, 8, 2, MAP_CLOSED_GATE if gate_closed else MAP_OPEN_GATE)
        if player is not None:
            self.draw_map_heading(*map_point(player.x, player.y), player.aim_angle)

        compass_x, compass_y = left + 28, top - 36
        self.font.draw(compass_x - 4, compass_y + 18, "N", WHITE)
        p.draw_line(compass_x, compass_y - 10, compass_x, compass_y + 8, *WHITE)
        p.draw_line(compass_x - 4, compass_y + 2, compass_x, compass_y + 8, *WHITE)
        p.draw_line(compass_x + 4, compass_y + 2, compass_x, compass_y + 8, *WHITE)
        rectangle(left, bottom, right - left, top - bottom, MAP_BORDER, filled=False)

    def draw_map(self, player):
        world = self.delivery
        p.SDL_SetRenderDrawColor(p.renderer, *MAP_INK, 255)
        p.SDL_RenderClear(p.renderer)
        self.draw_town_map(world.contract, 64, 104, 792, 528, player)
        self.font.draw(64, 674, "배달 구역 지도", WHITE)

        side = 880
        rectangle(side, 104, 336, 528, MAP_PANEL)
        rectangle(side, 104, 336, 528, MAP_BORDER, filled=False)
        self.font.draw(side + 24, 602, "다음 목표", WHITE)
        if len(world.contract.stops) > 1:
            self.font.draw(side + 238, 602, f"{len(world.completed_stops)} / {len(world.contract.stops)}", TEAL)
        waiting = world.parcel == "waiting"
        objective, target, accent = (
            ("택배 수령", "주황색 수령지에서 E", ORANGE) if waiting
            else ("택배 전달", "청록색 배송지에서 E", TEAL)
        )
        self.font.draw(side + 24, 566, objective, accent)
        self.font.draw(side + 24, 532, target, WHITE)
        p.draw_line(side + 24, 504, side + 312, 504, *MAP_BORDER)
        self.font.draw(side + 24, 474, "지도 범례", WHITE)
        for y, label, color, w, h in (
            (432, "큰길", MAP_ROAD, 24, 9),
            (394, "골목", MAP_ALLEY, 24, 5),
            (356, "건물", MAP_BUILDING, 18, 14),
            (318, "상점·정류장", MAP_LANDMARK, 18, 14),
            (242, "수령지", ORANGE, 8, 8),
            (204, "배송지", TEAL, 8, 8),
            (166, "폐차", MAP_WRECK, 18, 8),
        ):
            rectangle(side + 36 - w / 2, y - h / 2, w, h, color)
            self.font.draw(side + 62, y, label, WHITE)
        if DELIVERY_CONTRACTS[1].stops[0] in world.contract.stops:
            gate_closed = world.gate is not None
            rectangle(side + 24, 126, 24, 4, MAP_CLOSED_GATE if gate_closed else MAP_OPEN_GATE)
            self.font.draw(side + 62, 128, "철문 · 닫힘" if gate_closed else "철문 · 열림", WHITE)
        self.draw_map_heading(side + 31, 280, 0)
        self.font.draw(side + 62, 280, "현재 위치·방향", WHITE)
        rectangle(64, 40, 29, 27, MAP_PANEL)
        rectangle(64, 40, 29, 27, MAP_BORDER, filled=False)
        self.font.draw(73, 54, "M", WHITE)
        self.font.draw(105, 54, "닫기 · 지도 확인 중 일시정지", WHITE)

    def draw_ground_light(self, light, outline, edge, falloff, *, feathered=False):
        if feathered:
            samples, indices = feathered_beam_mesh(light, outline)
        else:
            samples = [(light.origin, 255)] + [(point, 255) for point, _ in outline]
            indices = [index for i in range(1, len(samples) - 1) for index in (0, i, i + 1)]
        if not indices:
            return

        ground = self.neighborhood_ground
        world_w, world_h = light.world_size
        vertices = (p.SDL_Vertex * len(samples))()
        for i, (point, opacity) in enumerate(samples):
            x, y = self.project(*point)
            strength = max(0, 1.0 - math.dist(light.origin, point) / light.radius)
            light_rgb = tuple(base + gain * strength for base, gain in zip(edge, falloff))
            uv = p.SDL_FPoint()
            if ground is not None:
                light_rgb = tuple(channel * 255 / GROUND_NEUTRAL for channel in light_rgb)
                uv = p.SDL_FPoint(max(0, min(1, point[0] / world_w)), max(0, min(1, 1 - point[1] / world_h)))
            color = p.SDL_Color(*(round(channel) for channel in light_rgb), opacity)
            vertices[i] = p.SDL_Vertex(p.SDL_FPoint(x, WINDOW_HEIGHT - 1 - y), color, uv)
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

    def wall(self, wall, outlines, beam_mask=None, *, glow_outline=()):
        x, y = self.project(wall.x, wall.y)
        height = wall_height(wall)
        depth = wall.depth * GROUND_SCALE_Y
        if x >= WINDOW_WIDTH or x + wall.width <= 0 or y >= WINDOW_HEIGHT or y + height + depth <= 0:
            return

        textured = isinstance(wall, NeighborhoodWall)
        image = self.neighborhood_walls.get(wall.texture) if textured else None
        oblique = image is not None and wall.oblique
        low_obstacle = image is not None and wall.texture in LOW_OBSTACLE_TEXTURES
        seam = (image.h - round(height / 2)) / image.h if image is not None else 0.5
        if oblique:
            front, side, roof = house_planes(wall, x, y)
            foundation = quad(x, y, wall.width, depth + HOUSE_FOUNDATION_HEIGHT)
            for plane in (foundation, front, side, roof):
                self.draw_wall_plane(None, plane, 0, 1, (0, 0, 0))
        else:
            front = quad(x, y, wall.width, height)
            roof = quad(x, y + height, wall.width, depth)
            if low_obstacle:
                self.draw_wall_plane(image, front, seam, 1, (0, 0, 0))
                self.draw_wall_plane(image, roof, 0, seam, (0, 0, 0))
            else:
                self.draw_wall_plane(None, quad(x, y, wall.width, height + depth), 0, 1, (0, 0, 0))

        front_band = min(1, ROOF_LIGHT_BAND / depth)
        side_band = min(1, ROOF_LIGHT_BAND / (front[1][0] - front[0][0]))
        edges = (
            (1, wall.y, wall.x, wall.width, "front"),
            (1, wall.y + wall.depth, wall.x, wall.width, "back"),
            (0, wall.x, wall.y, wall.depth, "left"),
            (0, wall.x + wall.width, wall.y, wall.depth, "right"),
        )
        strong_shades = ((178, 147, 105), (140, 123, 102), (155, 131, 103)) if image is not None else (
            (53, 47, 40), (45, 41, 38), (155, 131, 103))
        passes = []
        if glow_outline:
            dim_shades = tuple(map(dim_color, strong_shades))
            passes.extend((edge, glow_outline, None, dim_shades) for edge in edges)
        passes.extend((edge, outline, beam_mask if index == 0 else None, strong_shades)
                      for edge in edges for index, outline in enumerate(outlines))
        for (axis, boundary, offset, length, edge), outline, mask, shades in passes:
            facade_shade, roof_shade, side_shade = shades
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
                        self.draw_wall_plane(side_image, side, 0, 1, side_shade, (start, 0, end, 1), mask=mask)
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
            self.sprint_pulse_remaining = NOISE_PULSE_DURATION
        else:
            self.sprint_pulse_remaining = max(0.0, self.sprint_pulse_remaining - dt)

    def update_bottle_pulse(self, dt, position=None):
        if position is not None:
            self.bottle_pulse = position
            self.bottle_pulse_remaining = NOISE_PULSE_DURATION
        else:
            self.bottle_pulse_remaining = max(0.0, self.bottle_pulse_remaining - dt)

    def update_vehicle_alarm(self, dt, position=None):
        if position is not None:
            self.vehicle_alarm = position
            self.vehicle_alarm_remaining = VEHICLE_ALARM_DURATION
        else:
            self.vehicle_alarm_remaining = max(0.0, self.vehicle_alarm_remaining - dt)
            if not self.vehicle_alarm_remaining:
                self.vehicle_alarm = None

    def draw_noise_pulse(self, position, remaining, color, *, duration=NOISE_PULSE_DURATION):
        if remaining <= 0:
            return
        progress = 1.0 - remaining / duration
        radius = 18 + progress * 32
        x, y = position
        points = [(x + radius * dx, y + radius * dy) for dx, dy in PULSE_RING]
        color = tuple(round(bright + (floor - bright) * progress)
                      for bright, floor in zip(color, (48, 41, 34)))
        visible = [self.light.contains(point) for point in points]
        for index, (start, end) in enumerate(zip(points, points[1:])):
            if visible[index] and visible[index + 1]:
                p.draw_line(*self.project(*start), *self.project(*end), *color)

    def draw_lit_region(self, bounds, draw, *, row_spans=None):
        left, bottom, width, height = bounds
        right = min(WINDOW_WIDTH, math.ceil(left + width))
        left = max(0, math.floor(left))
        top = max(0, math.floor(WINDOW_HEIGHT - bottom - height - 1))
        end = min(WINDOW_HEIGHT, math.ceil(WINDOW_HEIGHT - bottom))
        if left >= right or top >= end:
            return
        if row_spans is None:
            row_spans = self.light_rows.__getitem__
        clipped = False
        previous, first = (), top
        try:
            for row in range(top, end + 1):
                spans = tuple((max(left, a), min(right, b)) for a, b in row_spans(row)
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

    def glow_at_ground_depth(self, position, screen_x):
        """Keep upright pixels inside the light and the object's ground-depth shadow."""
        if self.glow_source is None:
            return None
        glow, rows = self.glow_source
        columns = light_depth_columns(glow, position[1], screen_x - position[0])
        if not columns:
            return None
        return lambda row: clip_light_columns(rows.get(row, ()), columns)

    def draw_lit_prop(self, position, image, *, lift=0):
        x, y = self.project(*position)
        y += lift
        width, height = image.w * 2, image.h * 2
        bounds = (x - image.w, y, width, height)

        def draw():
            image.draw(x, y + image.h, width, height)

        glow_spans = self.glow_at_ground_depth(position, x)
        if glow_spans is not None:
            self.draw_lit_region(bounds, lambda: draw_dimmed_texture(image.texture, draw),
                                 row_spans=glow_spans)
        self.draw_lit_region(bounds, draw)

    def draw_station(self, position, pickup):
        x, y = self.project(*position)

        def draw_box(dimmed=False):
            if pickup:
                parts = ((-14, 0, 28, 23, (138, 86, 47)), (-14, 23, 28, 8, (186, 132, 76)),
                         (-3, 11, 6, 20, (226, 185, 106)))
            else:
                parts = ((-17, 0, 34, 43, (37, 100, 96)), (-17, 43, 34, 5, (86, 155, 145)),
                         (-11, 25, 22, 5, (11, 29, 34)))
            for dx, dy, width, height, color in parts:
                rectangle(x + dx, y + dy, width, height, dim_color(color) if dimmed else color)

        half_width = 14 if pickup else 17
        bounds = (x - half_width, y, half_width * 2 + 1, 32 if pickup else 49)
        glow_spans = self.glow_at_ground_depth(position, x)
        if glow_spans is not None:
            self.draw_lit_region(bounds, lambda: draw_box(dimmed=True), row_spans=glow_spans)
        self.draw_lit_region(bounds, draw_box)
        if self.light.contains(position):
            rectangle(x + 19, y + 26, 50, 23, (16, 24, 28))
            self.font.draw(x + 26, y + 37, "수령" if pickup else "배달", ORANGE if pickup else TEAL)

    def draw_delivery_result(self):
        self.play_hud.draw_result(self.delivery)

    def draw_lit_zombie(self, zombie, combat, attack):
        x, y = self.project(zombie.x, zombie.y)
        bounds = self.combat_visual.zombie_rect(zombie, x, y)

        def draw():
            self.combat_visual.draw_zombie(zombie, x, y)

        glow_spans = self.glow_at_ground_depth((zombie.x, zombie.y), x)
        if glow_spans is not None:
            def draw_glow():
                draw_dimmed_texture(self.combat_visual.zombie_texture(zombie), draw)

            def zombie_glow_spans(row):
                sample = zombie_light_row(row, y) if zombie.alive else row
                return glow_spans(sample)

            self.draw_lit_region(bounds, draw_glow, row_spans=zombie_glow_spans)

        row_spans = None
        if zombie.alive:
            left, _, width, _ = bounds
            if left + width <= 0 or left >= WINDOW_WIDTH:
                return
            origin_x = x - zombie.x
            sources = []
            for light, rows in self.light_sources:
                columns = light_depth_columns(light, zombie.y, origin_x)
                if columns:
                    sources.append((rows, columns))
            if not sources:
                return

            def zombie_row_spans(row):
                sample = zombie_light_row(row, y)
                return merge_light_spans(span for rows, columns in sources
                                         for span in clip_light_columns(rows.get(sample, ()), columns))

            row_spans = zombie_row_spans

        self.draw_lit_region(bounds, draw, row_spans=row_spans)
        self.draw_zombie_markers(zombie, combat, attack, x, y, row_spans=row_spans)

    def draw_zombie_markers(self, zombie, combat, attack, x, y, *, row_spans=None):
        scale = self.combat_visual.display_scale
        if combat.result == "playing" and zombie.alive and zombie.state in ZOMBIE_MARKS:
            symbol, color = ZOMBIE_MARKS[zombie.state]
            left, bottom = x + 24 * scale, y + 96 * scale

            def draw_status():
                rectangle(left, bottom, 18, 18, (16, 24, 28))
                self.font.draw(left + 4, bottom + 9, symbol, color)

            self.draw_lit_region((left, bottom - 2, 19, 23), draw_status, row_spans=row_spans)
        if (attack is not None and attack.facing == "front_right"
                and attack.elapsed < attack.hit_time + HIT_MARK_DURATION
                and any(target is zombie for target in attack.hit_targets)):
            x, y = x - 12 * scale, y + 83 * scale

            def draw_hit():
                p.draw_line(x - 9, y + 4, x - 3, y + 1, *WHITE)
                p.draw_line(x - 2, y + 9, x, y + 3, *ORANGE)
                p.draw_line(x + 4, y + 4, x + 9, y + 2, *WHITE)

            self.draw_lit_region((x - 9, y, 20, 10), draw_hit, row_spans=row_spans)

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
        glow = nearby_glow(origin, walls, world_size)
        glow_outline = glow.outline()
        glow_walls = {id(wall) for wall in glow.walls}
        # Only the stronger sources reveal targeting, station prompts and status marks.
        self.glow_source = (glow, light_source_rows(glow, self.project))
        lamps = tuple(self.streetlights_in_view())
        self.light = LightField((beam, *lamps))
        self.light_sources = tuple((source, light_source_rows(source, self.project)) for source in self.light.lights)
        self.light_rows = combined_light_rows([rows for _, rows in self.light_sources])
        beam_outline = beam.outline()
        # The ground cone ends at a wall's foot. Use the beam's shape before that collision
        # to clip the visible face, while the hit outline still selects which face gets light.
        open_beam = Flashlight(origin, beam.angle, (), world_size)
        beam_mask = []
        for point in (origin, *(point for point, _ in open_beam.outline())):
            x, y = self.project(*point)
            beam_mask.append((x, y + 1))
        lamp_outlines = tuple(lamp.outline() for lamp in lamps)
        self.draw_ground_light(glow, glow_outline, (0, 0, 0), NEARBY_GLOW_COLOR)
        self.draw_ground_light(beam, beam_outline, (28, 26, 23), (104, 84, 53), feathered=True)
        self.draw_streetlight_pools(lamps, lamp_outlines)
        outlines = (beam_outline, *lamp_outlines)
        self.draw_noise_pulse(self.sprint_pulse, self.sprint_pulse_remaining, TEAL)
        self.draw_noise_pulse(self.bottle_pulse, self.bottle_pulse_remaining, ORANGE)
        self.draw_noise_pulse(self.vehicle_alarm, self.vehicle_alarm_remaining, ORANGE,
                              duration=VEHICLE_ALARM_DURATION)
        foot = self.project(*origin)
        combat = getattr(self, "combat", None)
        attack = combat.attack if combat is not None else None
        delivery = self.delivery
        courier_style = {"empty_handed": delivery.parcel != "carrying"} if delivery is not None else {}
        bottles = []
        stations = ()
        if delivery is not None:
            stations = ((delivery.pickup,) if delivery.parcel == "waiting"
                        else tuple(stop.position for stop in delivery.remaining_stops))
            bottles.extend((x, y, 0) for x, y in delivery.bottle_pickups)
            flight = delivery.bottle_flight
            if flight is not None:
                progress = flight.progress
                x, y = (start + (end - start) * progress for start, end in zip(flight.origin, flight.destination))
                lift = (1 - progress) * (18 + 88 * progress)
                bottles.append((x, y, lift))
        for kind, actor in sorted_drawables(player, walls, zombies=combat.zombies if combat else (),
                                            prop=TRASH_CAN_POSITION if delivery is None else None,
                                            stations=stations,
                                            lamps=(lamp.origin for lamp in lamps),
                                            street_props=delivery.props if delivery is not None else (),
                                            bottles=bottles):
            if kind == "prop":
                self.draw_lit_prop(actor, self.trash_can)
            elif kind == "street-prop":
                self.draw_lit_prop((actor.x, actor.y), self.street_prop_images[actor.texture])
            elif kind == "bottle":
                x, y, lift = actor
                self.draw_lit_prop((x, y), self.street_prop_images["empty-bottle"], lift=lift)
            elif kind == "station":
                self.draw_station(actor, delivery.parcel == "waiting")
            elif kind == "lamp":
                self.draw_lit_prop(actor, self.streetlamp_image)
            elif kind == "wall":
                if not building_covers_player(actor, player, self.camera):
                    self.wall(actor, outlines, beam_mask, glow_outline=glow_outline if id(actor) in glow_walls else ())
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
        if delivery is not None:
            if delivery.result == "playing":
                near_visible_zombie = False
                if focused and self.play_hud.watch_for_sneak_hint(delivery):
                    for zombie in delivery.zombies:
                        position = zombie.x, zombie.y
                        if (zombie.alive and math.dist(origin, position) <= SNEAK_HINT_RANGE
                                and (self.light.contains(position) or glow.contains(position))
                                and delivery._player_line_clear(zombie)):
                            near_visible_zombie = True
                            break
                self.play_hud.draw(delivery, self.light, aim, focused=focused,
                                   alarm=self.vehicle_alarm_remaining > 0, near_visible_zombie=near_visible_zombie)
            else:
                self.draw_delivery_result()
            return

        self.font.draw(24, 683, "Dead Route  |  전투 검수", WHITE)
        self.font.draw(24, 651, "WASD 이동 · Shift 달리기 · Ctrl 잠행 · 마우스 조준 · 좌클릭 공격 · R 재시작 · Esc 종료", WHITE)
        if combat is not None:
            self.font.draw(24, 620, f"HP {combat.player_hp}/3", WHITE)
            self.font.draw(24, 592, "스태미나", WHITE)
            rectangle(116, 585, 100, 10, (48, 63, 71))
            stamina_width = round(100 * combat.stamina / MAX_STAMINA)
            if stamina_width:
                rectangle(116, 585, stamina_width, 10, TEAL)
            if combat.sneaking:
                self.font.draw(236, 592, "잠행 · 작은 발소리", TEAL)
            if combat.result != "playing":
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


def cutscene_controls():
    skip = lost_focus = False
    for event in poll_events():
        if event.type == p.SDL_QUIT:
            return None
        if event.type == p.SDL_KEYDOWN and not event.key.repeat:
            if event.key.keysym.sym == p.SDLK_ESCAPE:
                return None
            if event.key.keysym.sym in (p.SDLK_RETURN, p.SDLK_KP_ENTER):
                skip = True
        if (event.type == p.SDL_WINDOWEVENT
                and event.window.event == p.SDL_WINDOWEVENT_FOCUS_LOST):
            lost_focus = True
    return skip, lost_focus


def play_opening(renderer, music, art=None):
    start = previous = time.perf_counter()
    while True:
        now = time.perf_counter()
        controls = cutscene_controls()
        if controls is None:
            return False
        skip, lost_focus = controls
        elapsed = now - start
        if skip or elapsed >= opening.DURATION:
            return True
        focused = bool(p.SDL_GetWindowFlags(p.window) & p.SDL_WINDOW_INPUT_FOCUS)
        music.update(min(now - previous, 0.05), opening=True, focused=focused and not lost_focus)
        opening.draw(elapsed, renderer.font, renderer.player_visual, renderer.combat_visual.metadata["zombie"], art)
        p.update_canvas()
        previous = now


def play_ending(renderer, art, world, audio, *, player_hit):
    delivered = world.result == "delivered"
    duration = opening.ENDING_DURATION if delivered else opening.FAILURE_DURATION
    start = time.perf_counter()
    cue_played = False
    audio.stop()
    try:
        while True:
            elapsed = time.perf_counter() - start
            controls = cutscene_controls()
            if controls is None:
                return False
            skip, lost_focus = controls
            focused = bool(p.SDL_GetWindowFlags(p.window) & p.SDL_WINDOW_INPUT_FOCUS) and not lost_focus
            if not focused:
                audio.stop()
            elif not cue_played:
                if delivered:
                    audio.play_delivery_cue()
                elif player_hit:
                    audio.play_player_hit()
                cue_played = True
            if elapsed >= duration or (skip and focused):
                return True
            opening.draw_ending(elapsed, renderer.font, art, world)
            p.update_canvas()
    finally:
        audio.stop()


def run(smoke_test=False, *, show_opening=False, practice=False):
    renderer = None
    music = None
    zombie_audio = None
    cutscene_art = None
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
        if delivery_run:
            cutscene_art = opening.CutsceneArt(BASE_DIR / "assets/cutscenes")
        if not smoke_test:
            from spatial_audio import BackgroundMusic

            if show_opening:
                music = BackgroundMusic(BASE_DIR / "assets/audio/last-delivery.mp3")
                music.start()
                if not play_opening(renderer, music, cutscene_art):
                    return
            zombie_audio = ZombieAudio(BASE_DIR / "assets/audio")
        world = DeliveryWorld(two_stop_unlocked=load_two_stop_unlock()) if delivery_run else CombatWorld()
        renderer.combat = world
        if delivery_run:
            if music is not None:
                music.close()
            music = BackgroundMusic(BASE_DIR / "assets/audio/night-delivery-loop.ogg")
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
            pending_bottle_pickup = False
            pending_bottle_throw = False
            contract_choice = None
            preview_choice = renderer.delivery_preview
            reset_requested = False
            retry_requested = False
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
                            if key in DELIVERY_KEYS:
                                index = DELIVERY_KEYS[key]
                                if DELIVERY_CONTRACTS[index] in world.available_contracts:
                                    preview_choice = index
                            elif key in (p.SDLK_RETURN, p.SDLK_KP_ENTER):
                                contract_choice = preview_choice
                        continue
                    if key == p.SDLK_e and key not in pressed:
                        pending_interact = True
                    elif delivery_run and key == p.SDLK_f and key not in pressed:
                        pending_bottle_pickup = True
                    elif delivery_run and key == p.SDLK_q and key not in pressed:
                        pending_bottle_throw = True
                    elif key == p.SDLK_m and key not in pressed:
                        map_toggle = not map_toggle
                    elif (delivery_run and world.result != "playing"
                          and key in (p.SDLK_RETURN, p.SDLK_KP_ENTER)):
                        retry_requested = True
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
                retry_requested = False
            else:
                renderer.delivery_preview = preview_choice
            if reset_requested or retry_requested or contract_choice is not None:
                if contract_choice is not None:
                    world.select_contract(contract_choice)
                    if music is not None:
                        music.start()
                else:
                    world.reset()
                renderer.choosing_delivery = delivery_run and reset_requested
                if delivery_run:
                    renderer.reset_streetlights()
                    renderer.play_hud.reset_delivery()
                player, walls = world.player, world.walls
                renderer.player_visual.locomotion = Locomotion()
                renderer.combat_visual.reset_zombie_animation()
                pressed.clear()
                pending_click = False
                pending_interact = False
                pending_bottle_pickup = pending_bottle_throw = False
                mouse_held = False
                cursor = current_cursor()
                renderer.light = None
                renderer.map_open = False
                renderer.update_shake(math.inf)
                renderer.update_sprint_pulse(math.inf)
                renderer.update_bottle_pulse(math.inf)
                renderer.update_vehicle_alarm(math.inf)
                target = world.pickup if delivery_run else (world.zombie.x, world.zombie.y)
                aim_player(player, *target)
            elif map_toggle and focused and not lost_focus and delivery_run and world.result == "playing":
                renderer.map_open = not renderer.map_open
                if renderer.map_open and world.parcel == "carrying":
                    renderer.play_hud.dismiss_hint("M")
                pressed.clear()
                pending_click = pending_interact = mouse_held = False
                pending_bottle_pickup = pending_bottle_throw = False
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
                target = mouse_target(world, renderer.combat_visual, *cursor, light, renderer.camera,
                                      renderer.shake_offset, wall_alpha=renderer.wall_alpha)
            active = (focused and not lost_focus and not renderer.map_open
                      and contract_choice is None and not retry_requested)
            axis_x = int(p.SDLK_d in pressed) - int(p.SDLK_a in pressed)
            axis_y = int(p.SDLK_w in pressed) - int(p.SDLK_s in pressed)
            motion = renderer.player_visual.locomotion
            facing_hint = motion.facing if motion._initialized else None
            was_playing = world.result == "playing"
            swing_started = False
            if pending_click and active:
                facing = select_facing(player.aim_angle, facing_hint)
                swing_started = world.start_attack(facing=facing, stationary_front_right=True)
            if delivery_run and active:
                if pending_bottle_pickup:
                    world.pick_up_bottle()
                if pending_bottle_throw:
                    throw_target = sdl_to_world(*cursor, renderer.camera) if cursor is not None else target
                    world.throw_bottle(throw_target)
            before = (player.x, player.y)
            zombie_origins = [(zombie.x, zombie.y) for zombie in world.zombies]
            strike = world.attack
            was_landed = strike is not None and strike.landed
            hp_before = world.player_hp
            sprint = p.SDLK_LSHIFT in pressed or p.SDLK_RSHIFT in pressed
            sneak = p.SDLK_LCTRL in pressed or p.SDLK_RCTRL in pressed
            world.update(dt if active else 0.0, axis_x, axis_y, facing_hint=facing_hint, sprint=sprint, sneak=sneak)
            dx, dy = player.x - before[0], player.y - before[1]
            player_hit = world.player_hp < hp_before
            bottle_impact = world.bottle_impact if delivery_run and active else None
            renderer.update_bottle_pulse(dt if active else math.inf, bottle_impact)
            gate_opened = False
            if delivery_run and active and pending_interact:
                gate_was_closed = world.gate is not None
                if world.interact() and world.just_unlocked_two_stop:
                    save_two_stop_unlock()
                gate_opened = gate_was_closed and world.gate is None
                if gate_opened:
                    renderer.reset_streetlights()
            ending = delivery_run and was_playing and world.result in ("delivered", "defeated")
            audio_active = active and not reset_requested
            hearing_active = audio_active and world.result == "playing"
            renderer.update_sprint_pulse(dt if hearing_active else math.inf,
                                         world.sprint_step if hearing_active else None)
            vehicle_alarm = world.vehicle_alarm if delivery_run and hearing_active else None
            renderer.update_vehicle_alarm(dt if hearing_active else math.inf, vehicle_alarm)
            strike_landed = strike is not None and strike.landed and not was_landed
            strength = 0
            if player_hit:
                strength = 4
            elif strike_landed:
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
                music.update(dt, distance=distance, focused=active and (not delivery_run or world.result == "playing"))
            if zombie_audio is not None and not ending:
                occluded = hearing_active and nearest_zombie is not None and any(
                    wall_blocks((player.x, player.y), (nearest_zombie.x, nearest_zombie.y), wall)
                    for wall in walls)
                zombie_audio.update(dt, distance=distance if hearing_active else None, stride=stride, active=audio_active,
                                    occluded=occluded)
                if swing_started:
                    zombie_audio.play_bat_swing()
                if strike_landed:
                    zombie_audio.play_zombie_hit()
                if player_hit:
                    zombie_audio.play_player_hit()
                if bottle_impact is not None:
                    zombie_audio.play_bottle_break(math.dist((player.x, player.y), bottle_impact))
                if gate_opened:
                    zombie_audio.play_gate_open(math.dist((player.x, player.y), world.gate_position))
                if vehicle_alarm is not None:
                    zombie_audio.play_vehicle_alarm(math.dist((player.x, player.y), vehicle_alarm))
                if hearing_active:
                    zombie_audio.update_player_steps(math.hypot(dx, dy), sprinting=world.sprinting,
                                                    sneaking=world.sneaking)
            if smoke_test:
                name, player.x, player.y = smoke_poses[frame]
            previous_camera = renderer.camera
            renderer.follow(player)
            if cursor is not None and renderer.camera != previous_camera:
                target = mouse_target(world, renderer.combat_visual, *cursor, light, renderer.camera,
                                      renderer.shake_offset, wall_alpha=renderer.wall_alpha)
            if active and strike is None and world.result == "playing":
                aim_player(player, *target, max_turn=TURN_SPEED * dt)
            display_angle = world.attack.angle if world.attack is not None else player.aim_angle
            renderer.player_visual.update(display_angle, dx, dy, sprinting=delivery_run and world.sprinting)
            if ending:
                if not play_ending(renderer, cutscene_art, world, zombie_audio, player_hit=player_hit):
                    return
                pressed.clear()
                mouse_held = False
                cursor = current_cursor()
                focused = bool(p.SDL_GetWindowFlags(p.window) & p.SDL_WINDOW_INPUT_FOCUS)
                previous = time.perf_counter()
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
                    if cutscene_art is not None:
                        cutscene_art.close()
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
