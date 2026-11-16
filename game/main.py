"""Dead Route alley delivery, combat and flashlight rendering."""
from __future__ import annotations

import argparse
import ctypes
from dataclasses import replace
import math
from pathlib import Path
import time

import pico2d.pico2d as p

from core import WORLD_WIDTH, WORLD_HEIGHT, aim_player, wall_blocks
from combat import CombatWorld, HEAVY_ZOMBIE_APPEARANCE, MAX_STAMINA
from combat_visual import CombatVisual
from delivery import (DELIVERY_CONTRACTS, INTERACTION_RANGE, REAR_ALLEY_LISTEN_POINT, TOWN_ROADS, DeliveryWorld,
                      NeighborhoodWall)
from delivery_progress import load_two_stop_unlock, save_two_stop_unlock
from flashlight import Flashlight, LightField, feathered_beam_mesh, nearby_glow, nearby_glow_strength
from locomotion import Locomotion, select_facing
from play_hud import PlayHUD, SAFE_GREEN
from player_visual import PlayerVisual, load_atlas
from spatial_audio import HeavyFootstep, PatrolFootstep, ZombieAudio
from town_map_art import (MAP_ALLEY, MAP_BUILDING, MAP_ICON_ATLAS_SIZE, MAP_ICON_CLIPS, MAP_LANDMARK,
                          MAP_ROAD, MAP_WRECK)
from town_map_art import draw_base as draw_map_base
import opening

WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
GROUND_X = 160.0
GROUND_Y = 90.0
GROUND_SCALE_Y = 0.60
CAMERA_TIME = 0.145
CAMERA_LEAD_FRACTION = 0.25
CAMERA_MAX_LEAD = 72.0
RETURN_PERSPECTIVE_BOUNDS = (2470, 1220, 2650, 1410)
RETURN_PERSPECTIVE_BLEND = 36.0
RETURN_PERSPECTIVE_STRENGTH = .10
WALL_HEIGHT = 110
DELIVERY_CHARACTER_SCALE = 0.60
DELIVERY_KEYS = {p.SDLK_1: 0, p.SDLK_KP_1: 0, p.SDLK_2: 1, p.SDLK_KP_2: 1,
                 p.SDLK_3: 2, p.SDLK_KP_3: 2, p.SDLK_4: 3, p.SDLK_KP_4: 3}
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
WALL_TEXTURE_ALIASES = {"parking-shutter": "iron-gate"}
BRIDGE_TERRAIN = {"bridge-channel", "bridge-raised"}
LOW_OBSTACLE_TEXTURES = ("parked-car", "abandoned-car", "dumpster")
BUILDING_TEXTURES = {"west-house", "east-house", "shop", "workshop"}
BUILDING_FADE_OUT = .16
BUILDING_FADE_IN = .20
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
NEARBY_GLOW_COLOR = (118, 105, 87)
NEARBY_GLOW_TINT = 66
ZOMBIE_GLOW_BODY_PAD = 12.0
ZOMBIE_LIGHT_DEPTH_SCALE = 0.35
TRASH_CAN_POSITION = (365.0, 300.0)
WHITE = (231, 236, 231)
TEAL = (86, 225, 194)
ORANGE = (255, 182, 78)
MAP_INK = (14, 20, 23)
MAP_PANEL = (27, 39, 41)
MAP_BORDER = (91, 112, 112)
MAP_CLOSED_GATE = (204, 150, 104)
MAP_OPEN_GATE = (122, 188, 153)
MAP_PAPER_INK = (54, 57, 47)
MAP_LABEL = (249, 236, 203)
MAP_LABEL_EDGE = (163, 137, 100)
MAP_ROUTE_INK = (36, 73, 127)
MAP_ROUTE_HINT = (176, 205, 245)
MAP_ROAD_INK = (91, 75, 46)
MAP_ALLEY_INK = (100, 96, 81)
MAP_PICKUP = (168, 85, 27)
MAP_DROPOFF = (149, 45, 37)
MAP_SAFE = (42, 100, 57)
MAP_COMPLETED = (108, 114, 103)
MAP_VIEW_BG = (27, 23, 19)
MAP_VIEW_PANEL = (49, 39, 31)
MAP_VIEW_EDGE = (138, 111, 79)
MAP_VIEW_PAPER = (227, 211, 178)
MAP_VIEW_TEXT = (243, 228, 201)
PLAY_MAP_VIEWPORT = (64, 104, 792, 528)
HIT_MARK_DURATION = 0.14
FRONT_RIGHT_SWING_SOUND_DELAY = 0.060
NOISE_PULSE_DURATION = 0.24
VEHICLE_ALARM_DURATION = 1.2
AUDIO_PAN_NEAR_RADIUS = 72.0
REAR_ALLEY_LISTEN_RADIUS = 65.0
PULSE_RING = tuple((math.cos(i * math.tau / 24), math.sin(i * math.tau / 24)) for i in range(25))
ZOMBIE_MARKS = {"chase": ("!", ORANGE), "investigate": ("?", TEAL), "search": ("?", TEAL)}
SNEAK_HINT_RANGE = 160.0
TURN_SPEED = math.radians(450)
SHAKE_DURATIONS = {3: 0.08, 4: 0.10, 5: 0.12}
SHAKE_DIRECTIONS = ((1, 0), (-1, 1), (1, -1), (-1, 0))


def ground_offset(ground_scale):
    # Hold the center of the ground view steady while changing the camera pitch.
    return GROUND_Y + (GROUND_SCALE_Y - ground_scale) * WORLD_HEIGHT / 2


def world_to_screen(x, y, camera=(0.0, 0.0), *, ground_scale=GROUND_SCALE_Y):
    return GROUND_X + x - camera[0], ground_offset(ground_scale) + ground_scale * (y - camera[1])


def screen_to_world(x, y, camera=(0.0, 0.0), *, ground_scale=GROUND_SCALE_Y):
    return x - GROUND_X + camera[0], (y - ground_offset(ground_scale)) / ground_scale + camera[1]


def sdl_to_world(x, y, camera=(0.0, 0.0), *, ground_scale=GROUND_SCALE_Y):
    return screen_to_world(x, WINDOW_HEIGHT - 1 - y, camera, ground_scale=ground_scale)


def sound_position(listener, source):
    dx = source[0] - listener[0]
    distance = math.hypot(dx, source[1] - listener[1])
    return distance, dx / max(distance, AUDIO_PAN_NEAR_RADIUS)


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


def zombie_glow_opacity(glow, position):
    # Start fading in at the lit edge of the body before its foot reaches the ring.
    distance = math.dist(glow.origin, position) - ZOMBIE_GLOW_BODY_PAD
    return round(255 * nearby_glow_strength(distance))


def zombie_light_row(row, foot_y, ground_scale=GROUND_SCALE_Y):
    # A standing sprite's height only partially contributes to its ground depth.
    foot_row = WINDOW_HEIGHT - 1 - foot_y
    return math.floor(foot_row + (row + .5 - foot_row) * (ground_scale / GROUND_SCALE_Y)
                      * ZOMBIE_LIGHT_DEPTH_SCALE)


def light_depth_columns(light, ground_y, offset_x):
    return [(math.ceil(left + offset_x - .5), math.ceil(right + offset_x - .5))
            for left, right in light.spans_at(ground_y)]


def clip_light_columns(spans, columns):
    return [(max(left, start), min(right, stop)) for left, right in spans for start, stop in columns
            if left < stop and start < right]


def mouse_target(world, visual, mouse_x, mouse_y, light=None, camera=(0.0, 0.0), shake=(0, 0), *,
                 wall_alpha=None, building_opacity=None, nearby_light=None, ground_scale=GROUND_SCALE_Y):
    screen_y = WINDOW_HEIGHT - 1 - mouse_y
    for zombie in sorted(world.zombies, key=lambda enemy: enemy.y):
        position = (zombie.x, zombie.y)
        x, y = world_to_screen(*position, camera, ground_scale=ground_scale)
        if not visual.zombie_contains(zombie, x + shake[0], y + shake[1], mouse_x, screen_y):
            continue
        if light is not None:
            sample = zombie_light_row(mouse_y, y + shake[1], ground_scale)
            world_x, depth = screen_to_world(mouse_x + .5 - shake[0],
                                              WINDOW_HEIGHT - 1.5 - sample - shake[1], camera,
                                              ground_scale=ground_scale)
            sources = light.lights
            if nearby_light is not None and zombie_glow_opacity(nearby_light, position):
                sources = (*sources, nearby_light)
            if not any(any(left <= world_x < right for left, right in source.spans_at(zombie.y))
                       and any(left <= world_x < right for left, right in source.spans_at(depth))
                       for source in sources):
                continue
        # A wall drawn in front can cover the upper part of a lit sprite.
        wx, wy = mouse_x - shake[0], screen_y - shake[1]
        for wall in world.walls:
            if wall.y >= zombie.y:
                continue
            hidden = (building_opacity(wall) == 0 if building_opacity is not None
                      else building_covers_player(wall, world.player, camera, ground_scale=ground_scale))
            if hidden:
                continue
            left, bottom = world_to_screen(wall.x, wall.y, camera, ground_scale=ground_scale)
            alpha_rows = wall_alpha.get(wall.texture) if wall_alpha and isinstance(wall, NeighborhoodWall) else None
            if wall_covers(wall, left, bottom, wx, wy, alpha_rows, ground_scale=ground_scale):
                break
        else:
            return position
    return sdl_to_world(mouse_x, mouse_y, camera, ground_scale=ground_scale)


def wall_height(wall):
    return wall.height if isinstance(wall, NeighborhoodWall) else WALL_HEIGHT


def house_planes(wall, x, y, *, ground_scale=GROUND_SCALE_Y):
    depth = wall.depth * ground_scale
    inset = round(min(wall.width * .26, depth * .42))
    near_right = x + wall.width - inset
    far_right = x + wall.width
    top = y + wall.height
    return (
        ((x, y), (near_right, y), (near_right, top), (x, top)),
        ((near_right, y), (far_right, y + depth), (far_right, top + depth), (near_right, top)),
        ((x, top), (near_right, top), (far_right, top + depth), (x + inset, top + depth)),
    )


def wall_covers(wall, left, bottom, x, y, alpha_rows=None, *, ground_scale=GROUND_SCALE_Y):
    oblique = isinstance(wall, NeighborhoodWall) and wall.oblique
    if oblique or alpha_rows is not None:
        # SDL fills triangles at the pixel center.
        x, y = x + .5, y + .5
    height, depth = wall_height(wall), wall.depth * ground_scale
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
               for plane in house_planes(wall, left, bottom, ground_scale=ground_scale))


def building_covers_player(wall, player, camera, *, ground_scale=GROUND_SCALE_Y):
    if (not isinstance(wall, NeighborhoodWall) or wall.texture not in BUILDING_TEXTURES
            or player.y < wall.y + wall.depth):
        return False
    # The ground anchor keeps the cutaway stable across poses and held equipment.
    left, bottom = world_to_screen(wall.x, wall.y, camera, ground_scale=ground_scale)
    x, y = world_to_screen(player.x, player.y, camera, ground_scale=ground_scale)
    return wall_covers(wall, left, bottom, x, y, ground_scale=ground_scale)


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
        self.map_icons = None
        self.neighborhood_walls = {}
        self.wall_alpha = {}
        self._building_fades = {}
        self.street_prop_images = {}
        self.streetlamp_image = None
        self.streetlights = ()
        self.combat = None
        self.delivery = None
        self.cursor = None
        self.light = None
        self._light_pose = None
        self.glow_source = None
        self.nearby_light = None
        self.camera = (0.0, 0.0)
        self.choosing_delivery = False
        self.delivery_preview = 0
        self.map_open = False
        self.abandon_confirmation = False
        self.bridge_note_open = False
        self.shake_remaining = 0.0
        self.shake_strength = 0
        self.shake_offset = (0, 0)
        self.shake_axis = (1.0, 0.0)
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
            if not isinstance(wall, NeighborhoodWall) or wall.texture in BRIDGE_TERRAIN:
                continue
            texture = WALL_TEXTURE_ALIASES.get(wall.texture, wall.texture)
            if texture not in self.neighborhood_walls:
                self.neighborhood_walls[texture] = load_atlas(
                    NEIGHBORHOOD_PATH / f"{texture}.png", WALL_TEXTURE_SIZES[texture])
            if wall.oblique:
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
        self.map_icons = p.load_image(str(BASE_DIR / "assets/ui/town-map-icons.png"))
        if (self.map_icons.w, self.map_icons.h) != MAP_ICON_ATLAS_SIZE:
            raise ValueError("Town map icon atlas has incorrect dimensions")
        if p.SDL_SetTextureScaleMode(self.map_icons.texture, p.SDL_ScaleModeLinear) != 0:
            raise RuntimeError(f"Town map icon sampling failed: {p.SDL_GetError()!r}")
        self.reset_streetlights()
        self.play_hud = PlayHUD(BASE_DIR / "assets/ui/NotoSansKR-Regular.ttf", WINDOW_WIDTH, WINDOW_HEIGHT)

    def reset_streetlights(self):
        radius = STREETLIGHT_RADIUS
        lights = []
        for x, y in self.delivery.streetlights:
            walls = [wall for wall in self.delivery.walls
                     if getattr(wall, "texture", None) != "bridge-channel"
                     and x - radius <= wall.x + wall.width and wall.x <= x + radius
                     and y - radius <= wall.y + wall.depth and wall.y <= y + radius]
            lights.append(Flashlight((x, y), 0, walls, self.delivery.world_size,
                                     radius=radius, half_angle=math.pi))
        self.streetlights = tuple(lights)

    def streetlights_in_view(self):
        for light in self.streetlights:
            x, y = self.project(*light.origin)
            radius_y = light.radius * self.ground_scale()
            if -light.radius <= x <= WINDOW_WIDTH + light.radius and -radius_y <= y <= WINDOW_HEIGHT + radius_y:
                yield light

    def close(self):
        if self.play_hud is not None:
            self.play_hud.close()
            self.play_hud = None
        self.street_prop_images.clear()
        self.streetlamp_image = None
        self.neighborhood_ground = None
        self.map_icons = None
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

    def update_shake(self, dt, strength=0, *, hit_angle=None):
        if strength:
            self.shake_strength = strength
            self.shake_remaining = SHAKE_DURATIONS[strength]
            self.shake_axis = (1.0, 0.0)
            if hit_angle is not None:
                x, y = math.cos(hit_angle), self.ground_scale() * math.sin(hit_angle)
                length = math.hypot(x, y)
                self.shake_axis = x / length, y / length
        else:
            self.shake_remaining = max(0.0, self.shake_remaining - dt)
        self.shake_offset = (0, 0)
        if self.shake_remaining > 0:
            duration = SHAKE_DURATIONS[self.shake_strength]
            phase = int((duration - self.shake_remaining) / 0.014)
            dx, dy = SHAKE_DIRECTIONS[phase % len(SHAKE_DIRECTIONS)]
            amplitude = round(self.shake_strength * self.shake_remaining / duration)
            x, y = self.shake_axis
            self.shake_offset = (round((dx * x - dy * y) * amplitude), round((dx * y + dy * x) * amplitude))

    def project(self, x, y):
        sx, sy = world_to_screen(x, y, self.camera, ground_scale=self.ground_scale())
        dx, dy = self.shake_offset
        return sx + dx, sy + dy

    def perspective_strength(self):
        world = self.delivery
        if getattr(world, "contract", None) is not DELIVERY_CONTRACTS[3] or world.parcel != "delivered":
            return 0.0
        left, bottom, right, top = RETURN_PERSPECTIVE_BOUNDS
        x, y = world.player.x, world.player.y
        distance = min(x - left, right - x, y - bottom, top - y)
        if distance <= 0.0:
            return 0.0
        t = min(1.0, distance / RETURN_PERSPECTIVE_BLEND)
        return RETURN_PERSPECTIVE_STRENGTH * t * t * (3 - 2 * t)

    def ground_scale(self):
        return GROUND_SCALE_Y - self.perspective_strength()

    def cursor_world(self, cursor):
        if cursor is not None:
            return sdl_to_world(*cursor, self.camera, ground_scale=self.ground_scale())

    def follow(self, player, dt=None, *, cursor=None):
        if self.delivery is None:
            return
        width, height = self.delivery.world_size
        right, top = width - WORLD_WIDTH, height - WORLD_HEIGHT
        base = (min(max(0.0, player.x - WORLD_WIDTH / 2), right),
                min(max(0.0, player.y - WORLD_HEIGHT / 2), top))
        if dt is None:
            self.camera = base
            return

        destination = base
        if cursor is not None:
            ground_scale = self.ground_scale()
            # Measure from the unshifted foot so the lead never feeds itself.
            foot_x, foot_y = world_to_screen(player.x, player.y, base, ground_scale=ground_scale)
            dx = cursor[0] - foot_x
            dy = WINDOW_HEIGHT - 1 - cursor[1] - foot_y
            distance = math.hypot(dx, dy)
            if distance:
                factor = min(CAMERA_LEAD_FRACTION, CAMERA_MAX_LEAD / distance)
                destination = (min(max(0.0, base[0] + dx * factor), right),
                               min(max(0.0, base[1] + dy * factor / ground_scale), top))
        weight = -math.expm1(-dt / CAMERA_TIME)
        self.camera = tuple(current + (desired - current) * weight
                            for current, desired in zip(self.camera, destination))

    def prepare_light(self, player, walls, aim):
        origin = (player.x, player.y)
        dx, dy = aim[0] - origin[0], aim[1] - origin[1]
        angle = math.atan2(dy, dx) if dx or dy else player.aim_angle
        pose = (origin, angle, self.camera, self.shake_offset, self.ground_scale(), id(walls))
        if self.light is None or pose != self._light_pose:
            world_size = self.combat.world_size if self.combat is not None else (WORLD_WIDTH, WORLD_HEIGHT)
            light_walls = self.light_walls(walls)
            beam = Flashlight(origin, angle, light_walls, world_size)
            self.nearby_light = nearby_glow(origin, light_walls, world_size)
            self.light = LightField((beam, *self.streetlights_in_view()))
            self._light_pose = pose
        return self.light

    @staticmethod
    def light_walls(walls):
        return [wall for wall in walls if getattr(wall, "texture", None) != "bridge-channel"]

    def reset_building_fades(self):
        self._building_fades.clear()

    def building_opacity(self, wall):
        return self._building_fades.get(id(wall), 1.0)

    def update_building_fades(self, player, walls, dt):
        ground_scale = self.ground_scale()
        for wall in walls:
            key = id(wall)
            opacity = self.building_opacity(wall)
            if building_covers_player(wall, player, self.camera, ground_scale=ground_scale):
                remaining = opacity - dt / BUILDING_FADE_OUT
                self._building_fades[key] = 0.0 if remaining <= 1e-12 else remaining
            elif opacity < 1.0:
                opacity = opacity + dt / BUILDING_FADE_IN
                if opacity >= 1.0 - 1e-12:
                    self._building_fades.pop(key, None)
                else:
                    self._building_fades[key] = opacity

    def draw_delivery_selection(self):
        world = self.delivery
        p.SDL_SetRenderDrawColor(p.renderer, *MAP_INK, 255)
        p.SDL_RenderClear(p.renderer)
        self.font.draw(64, 672, "DEAD ROUTE  |  배달 선택", TEAL)
        rectangle(64, 104, 378, 528, MAP_PANEL)
        rectangle(64, 104, 378, 528, MAP_BORDER, filled=False)
        for index, contract in enumerate(DELIVERY_CONTRACTS):
            bottom = 521 - index * 92
            selected = index == self.delivery_preview
            accent = TEAL if selected else MAP_BORDER
            rectangle(82, bottom, 342, 84, (38, 56, 56) if selected else (18, 29, 32))
            rectangle(82, bottom, 342, 84, accent, filled=False)
            if contract not in world.available_contracts:
                self.font.draw(100, bottom + 62, f"[{index + 1}]  {contract.name} · 잠금", WHITE)
                self.font.draw(100, bottom + 30, "기존 배달 1회 성공 후 해금", WHITE)
                continue
            self.font.draw(100, bottom + 62, f"[{index + 1}]  {contract.name}", TEAL if selected else WHITE)
            self.font.draw(100, bottom + 40, f"난이도 · {contract.difficulty}", ORANGE)
            self.font.draw(100, bottom + 18, contract.description, WHITE)
        keys = " / ".join(str(i) for i, contract in enumerate(DELIVERY_CONTRACTS, 1)
                          if contract in world.available_contracts)
        self.font.draw(100, 201, f"{keys}  계약 선택", WHITE)
        self.font.draw(100, 162, "Enter  배달 시작  ·  Esc  종료", TEAL)

        contract = DELIVERY_CONTRACTS[self.delivery_preview]
        self.font.draw(496, 610, f"{contract.name} 지도", WHITE)
        self.draw_town_map(contract, 496, 104, 720, 480)
        for x, color, label, pickup in ((500, MAP_PICKUP, "수령지", True), (612, MAP_DROPOFF, "배송지", False)):
            self.draw_map_pin(x, 69, color, pickup=pickup)
            self.font.draw(x + 14, 69, label, WHITE)
        if DELIVERY_CONTRACTS[1].stops[0] in contract.stops:
            rectangle(720, 67, 10, 4, MAP_CLOSED_GATE)
            self.font.draw(736, 69, "철문", WHITE)
        if contract.return_point is not None:
            self.draw_safe_map_marker(724, 69, MAP_SAFE, backing=MAP_LABEL)
            self.font.draw(736, 69, "안전지점", WHITE)

    @staticmethod
    def draw_map_heading(x, y, angle, *, on_paper=False):
        dx, dy = math.cos(angle), math.sin(angle)
        tip_x, tip_y = x + 16 * dx, y + 16 * dy
        color = MAP_INK if on_paper else WHITE
        p.draw_line(x, y, tip_x, tip_y, *color)
        for side in (-1, 1):
            p.draw_line(tip_x, tip_y, tip_x - 6 * dx - 4 * dy * side,
                        tip_y - 6 * dy + 4 * dx * side, *color)
        rectangle(x - 4, y - 4, 8, 8, MAP_INK)
        rectangle(x - 2, y - 2, 4, 4, WHITE)

    @staticmethod
    def draw_map_pin(x, y, color, *, pickup=False):
        if pickup:
            rectangle(x - 6, y - 6, 12, 12, MAP_LABEL)
            rectangle(x - 4, y - 4, 8, 8, color)
        else:
            p.draw_circle(x, y, 9, *MAP_LABEL, filled=True)
            p.draw_circle(x, y, 7, *color, filled=True)
            p.draw_circle(x, y, 4, *MAP_LABEL, filled=True)
            rectangle(x - 1, y - 1, 2, 2, color)

    def draw_map_waypoint(self, x, y, number):
        label = str(number)
        half_width = 2 + 5 * len(label)
        rectangle(x - half_width - 1, y - 11, 2 * half_width + 2, 22, MAP_LABEL)
        rectangle(x - half_width, y - 10, 2 * half_width, 20, MAP_ROUTE_INK)
        self.font.draw(x - half_width + 2, y, label, MAP_LABEL)

    def draw_map_waypoints(self, bounds, points, first_number, occupied):
        left, bottom, right, top = bounds
        for index, (x, y) in enumerate(points, first_number):
            half_width = 3 + 5 * len(str(index))
            step = half_width + 13
            offsets = ((0, 0), (step, 0), (-step, 0), (0, 24), (0, -24),
                       (step, 24), (-step, 24), (step, -24), (-step, -24),
                       (2 * step, 0), (-2 * step, 0), (0, 48), (0, -48))
            for dx, dy in offsets:
                bx = min(right - half_width - 1, max(left + half_width + 1, x + dx))
                by = min(top - 12, max(bottom + 12, y + dy))
                west, south, east, north = bx - half_width, by - 11, bx + half_width, by + 11
                if all(east < a or west > c or north < b or south > d for a, b, c, d in occupied):
                    break
            occupied.append((west, south, east, north))
            if (bx, by) != (x, y):
                p.draw_line(x, y, bx, by, *MAP_ROUTE_INK)
            self.draw_map_waypoint(bx, by, index)

    def draw_map_label(self, x, y, width, label, color=MAP_PAPER_INK):
        rectangle(x, y, width, 23, MAP_LABEL)
        rectangle(x, y, width, 23, MAP_LABEL_EDGE, filled=False)
        self.font.draw(x + 7, y + 11, label, color)

    @staticmethod
    def draw_safe_map_marker(x, y, color=SAFE_GREEN, *, backing=None):
        if backing is not None:
            p.draw_circle(x, y, 8, *backing, filled=True)
        points = ((x, y + 7), (x + 7, y), (x, y - 7), (x - 7, y), (x, y + 7))
        for start, end in zip(points, points[1:]):
            p.draw_line(*start, *end, *color)
        rectangle(x - 2, y - 2, 4, 4, color)

    def _map_layout(self, x, y, viewport_width, viewport_height):
        width, height = self.delivery.world_size
        scale = min(viewport_width / width, viewport_height / height)
        left = x + (viewport_width - width * scale) / 2
        bottom = y + (viewport_height - height * scale) / 2
        return left, bottom, scale

    def map_world_at(self, mouse_x, mouse_y):
        """Convert an SDL mouse position inside the live map to ground coordinates."""
        left, bottom, scale = self._map_layout(*PLAY_MAP_VIEWPORT)
        x = (mouse_x - left) / scale
        y = (WINDOW_HEIGHT - 1 - mouse_y - bottom) / scale
        width, height = self.delivery.world_size
        if -1e-9 <= x <= width + 1e-9 and -1e-9 <= y <= height + 1e-9:
            return min(width, max(0.0, x)), min(height, max(0.0, y))
        return None

    def _draw_map_sprite(self, kind, left, bottom, width, height):
        clip = MAP_ICON_CLIPS.get(kind)
        if self.map_icons is None or clip is None:
            return False
        x, y = round(left), round(bottom)
        w, h = round(left + width) - x, round(bottom + height) - y
        if w > 0 and h > 0:
            self.map_icons.clip_draw_to_origin(*clip, x, y, w, h)
        return True

    def draw_town_map(self, contract, x, y, viewport_width, viewport_height, player=None):
        world = self.delivery
        width, height = world.world_size
        left, bottom, scale = self._map_layout(x, y, viewport_width, viewport_height)
        right = left + width * scale
        top = bottom + height * scale

        def map_point(x, y):
            return left + x * scale, bottom + y * scale

        active_contract = contract is world.contract
        shutter = world.shutter_wall if active_contract else None
        bridge = world.bridge_puzzle if active_contract else None
        show_east_detour = bridge is not None and player is not None and world.returning
        map_walls = [wall for wall in world.walls if getattr(wall, "texture", None) not in BRIDGE_TERRAIN]
        if contract is not world.contract and world.parking_walls:
            map_walls = [wall for wall in map_walls if wall is not world.shutter_wall
                         and wall not in (*world.parking_walls, *world.bridge_puzzle.station_walls)]
        draw_map_base(rectangle, p.draw_line, (left, bottom, right, top), scale, (width, height),
                      TOWN_ROADS, map_walls, draw_sprite=self._draw_map_sprite)
        for point, label, color in (
            ((720, 80), "남쪽 큰길", MAP_ROAD_INK),
            ((3140, 958) if show_east_detour else (3110, 1007), "상점길", MAP_ALLEY_INK),
            ((2440, 1720), "정류장길", MAP_ALLEY_INK),
        ):
            self.font.draw(*map_point(*point), label, color)

        route = []
        if player is not None:
            route = [map_point(player.x, player.y), *(map_point(*point) for point in world.waypoints)]
            for start, end in zip(route, route[1:]):
                for dx, dy in ((-1, 0), (0, -1), (1, 0), (0, 1)):
                    p.draw_line(start[0] + dx, start[1] + dy, end[0] + dx, end[1] + dy, *MAP_LABEL)
            for start, end in zip(route, route[1:]):
                p.draw_line(*start, *end, *MAP_ROUTE_INK)

        occupied = []
        labels = []
        landmark_labels = {"shop": "상점", "bus-stop": "정류장"}
        for wall in map_walls:
            label = landmark_labels.get(getattr(wall, "texture", None))
            if label:
                anchor_x, anchor_y = map_point(wall.x + wall.width / 2, wall.y + wall.depth)
                label_width = 17 * len(label) + 16
                x = min(right - label_width - 7, anchor_x + 16)
                if shutter is not None and label == "상점":
                    x = anchor_x - label_width - 12
                y = min(top - 29, anchor_y + 10)
                occupied.append((x, y, x + label_width, y + 23))
                leader_x = x + label_width if x < anchor_x else x
                p.draw_line(anchor_x, anchor_y, leader_x, y + 5, *MAP_PAPER_INK)
                labels.append((x, y, label_width, label, MAP_PAPER_INK))

        pickup_x, pickup_y = map_point(*contract.pickup)
        occupied.append((pickup_x - 7, pickup_y - 7, pickup_x + 7, pickup_y + 7))
        pickup_done = contract.return_point is not None and player is not None and world.parcel != "waiting"
        self.draw_map_pin(pickup_x, pickup_y, MAP_COMPLETED if pickup_done else MAP_PICKUP, pickup=True)
        for stop in contract.stops:
            completed = player is not None and stop in world.completed_stops
            color = MAP_COMPLETED if completed and contract.return_point is None else MAP_DROPOFF
            x, y = map_point(*stop.position)
            occupied.append((x - 9, y - 9, x + 9, y + 9))
            self.draw_map_pin(x, y, color)
            label = stop.name
            if player is not None and (len(contract.stops) > 1 or completed and world.returning):
                label += " · 완료" if completed else " · 미완료"
            label_width = 17 * len(label) + 16
            label_x = max(left + 4, x - label_width - 10)
            if contract.return_point is not None:
                label_x = min(right - label_width - 4, max(x, pickup_x) + 10)
            label_y = max(bottom + 4, y - 32)
            occupied.append((label_x, label_y, label_x + label_width, label_y + 23))
            leader_x = label_x if label_x > x else label_x + label_width
            p.draw_line(x, y - 7, leader_x, label_y + 19, *color)
            labels.append((label_x, label_y, label_width, label, color))
        if contract.return_point is not None:
            safe_x, safe_y = map_point(*contract.return_point)
            occupied.append((safe_x - 94, safe_y - 11, safe_x - 11, safe_y + 12))
            occupied.append((safe_x - 8, safe_y - 8, safe_x + 8, safe_y + 8))
            self.draw_safe_map_marker(safe_x, safe_y, MAP_SAFE, backing=MAP_LABEL)
            labels.append((safe_x - 94, safe_y - 11, 83, "안전지점", MAP_SAFE))
        if DELIVERY_CONTRACTS[1].stops[0] in contract.stops:
            gate_x, gate_y = map_point(*world.gate_position)
            gate_closed = player is None or world.gate is not None
            rectangle(gate_x - 5, gate_y - 7, 10, 4, MAP_INK)
            rectangle(gate_x - 4, gate_y - 6, 8, 2, MAP_CLOSED_GATE if gate_closed else MAP_OPEN_GATE)
        if shutter is not None:
            sx, sy = map_point(shutter.x, shutter.y)
            marker_w, marker_h = max(4, shutter.width * scale), max(4, shutter.depth * scale)
            color = MAP_CLOSED_GATE if world.shutter_closed else MAP_OPEN_GATE
            rectangle(sx - 1, sy - 1, marker_w + 2, marker_h + 2, MAP_INK)
            rectangle(sx, sy, marker_w, marker_h, color)
            occupied.append((sx - 1, sy - 1, sx + marker_w + 1, sy + marker_h + 1))
            lot_x, lot_y = map_point(*world.shutter_lure)
            label_x, label_y = lot_x - 32, lot_y + 5
            occupied.append((label_x, label_y, label_x + 65, label_y + 23))
            p.draw_line(lot_x, lot_y, lot_x, label_y, *MAP_PAPER_INK)
            labels.append((label_x, label_y, 65, "주차장", MAP_PAPER_INK))
        if bridge is not None:
            x, y, width, depth = bridge.channel_rect
            cx, cy = map_point(x, y)
            rectangle(cx, cy, width * scale, max(2, depth * scale), MAP_ROUTE_INK)
            next_stop = self.bridge_map_next_stop(world) if player is not None else None
            for position, symbol in ((bridge.key_position, "K"), (bridge.panel_position, "C")):
                px, py = map_point(*position)
                active = next_stop is not None and symbol == next_stop[0]
                self.draw_bridge_map_marker(px, py, symbol, active=active)
                half_w, half_h = (9, 10) if active else (7, 8)
                occupied.append((px - half_w, py - half_h, px + half_w, py + half_h))
                if active:
                    label = next_stop[1]
                    label_x, label_y = px + 16, py - 11
                    label_width = 17 * len(label) + 16
                    p.draw_line(px + 9, py, label_x, py, *MAP_PICKUP)
                    labels.append((label_x, label_y, label_width, label, MAP_PICKUP))
                    occupied.append((label_x, label_y, label_x + label_width, label_y + 23))
            bx, by = map_point(*bridge.bridge_position)
            if bridge.bridge_down:
                bridge_x, bridge_y, bridge_width, bridge_depth = bridge.bridge_rect
                deck_x, deck_y = map_point(bridge_x, bridge_y)
                deck_width, deck_depth = bridge_width * scale, bridge_depth * scale
                rectangle(deck_x, deck_y, deck_width, deck_depth, MAP_OPEN_GATE)
                rectangle(deck_x, deck_y, deck_width, deck_depth, MAP_SAFE, filled=False)
                p.draw_line(bx, deck_y - 4, bx, deck_y + deck_depth + 4, *MAP_SAFE)
                label_x, label_y = cx + width * scale + 10, by + 6
                p.draw_line(bx, deck_y + deck_depth + 4, label_x, label_y + 8, *MAP_SAFE)
                labels.append((label_x, label_y, 118, "다리 지름길", MAP_SAFE))
                occupied.append((label_x, label_y, label_x + 118, label_y + 23))
            else:
                rectangle(bx - 9, by - 4, 18, 8, MAP_INK)
                rectangle(bx - 7, by - 2, 14, 4, MAP_CLOSED_GATE)
            half_h = 9 if bridge.bridge_down else 4
            occupied.append((bx - 9, by - half_h, bx + 9, by + half_h))
            if show_east_detour:
                # The completed delivery label covers the turn at y=987. Mark the same lane just north of it.
                entry_x, entry_y = map_point(2750, 1058)
                arrow_y = entry_y + 12
                detour_ink = (39, 93, 90)
                p.draw_line(entry_x, entry_y - 6, entry_x, arrow_y, *detour_ink)
                for dx in (-4, 4):
                    p.draw_line(entry_x, arrow_y, entry_x + dx, arrow_y - 5, *detour_ink)
                label_x, label_y, label_width = entry_x + 74, entry_y + 1, 101
                p.draw_line(entry_x + 4, entry_y + 1, label_x, label_y + 11, *detour_ink)
                labels.append((label_x, label_y, label_width, "동쪽 우회", detour_ink))
                occupied.append((entry_x - 4, entry_y - 6, entry_x + 4, arrow_y))
                occupied.append((label_x, label_y, label_x + label_width, label_y + 23))
        if player is not None:
            self.draw_map_waypoints((left, bottom, right, top), route[1:], world.first_waypoint_number, occupied)
            self.draw_map_heading(*route[0], player.aim_angle, on_paper=True)
        for label in labels:
            self.draw_map_label(*label)

        compass_x, compass_y = left + 31, top - 39
        p.draw_circle(compass_x, compass_y, 17, *MAP_LABEL, filled=True)
        p.draw_circle(compass_x, compass_y, 17, *MAP_LABEL_EDGE)
        self.font.draw(compass_x - 5, compass_y + 24, "N", MAP_PAPER_INK)
        p.draw_line(compass_x, compass_y - 9, compass_x, compass_y + 9, *MAP_PAPER_INK)
        p.draw_line(compass_x - 5, compass_y + 2, compass_x, compass_y + 9, *MAP_PAPER_INK)
        p.draw_line(compass_x + 5, compass_y + 2, compass_x, compass_y + 9, *MAP_PAPER_INK)
        scale_x, scale_y = left + 60, compass_y - 6
        half_scale = 200 * scale
        rectangle(scale_x, scale_y, half_scale, 4, MAP_PAPER_INK)
        rectangle(scale_x + half_scale, scale_y, half_scale, 4, MAP_LABEL)
        rectangle(scale_x, scale_y, 2 * half_scale, 4, MAP_PAPER_INK, filled=False)
        self.font.draw(scale_x, scale_y + 15, "400 px", MAP_PAPER_INK)
        rectangle(left, bottom, right - left, top - bottom, MAP_BORDER, filled=False)

    @staticmethod
    def bridge_map_next_stop(world):
        bridge = world.bridge_puzzle
        if not world.returning or bridge is None or bridge.bridge_down:
            return None
        if bridge.has_key:
            return "C", "관리실", "회로 연결"
        return "K", "경비초소", "열쇠 찾기"

    def draw_bridge_map_marker(self, x, y, symbol, *, active=False):
        if active:
            rectangle(x - 9, y - 10, 18, 20, MAP_PICKUP)
        rectangle(x - 7, y - 8, 14, 16, MAP_LABEL)
        if not active:
            rectangle(x - 7, y - 8, 14, 16, MAP_PAPER_INK, filled=False)
        self.font.draw(x - 5, y, symbol, MAP_PAPER_INK)

    def draw_map(self, player):
        world = self.delivery
        p.SDL_SetRenderDrawColor(p.renderer, *MAP_VIEW_BG, 255)
        p.SDL_RenderClear(p.renderer)
        self.draw_town_map(world.contract, *PLAY_MAP_VIEWPORT, player)
        rectangle(64, 650, 1152, 48, MAP_VIEW_PAPER)
        rectangle(64, 650, 1152, 48, MAP_VIEW_EDGE, filled=False)
        self.font.draw(82, 674, "배달 구역 지도", MAP_PAPER_INK)
        self.font.draw(1012, 674, "지도 확인 중 일시정지", MAP_PAPER_INK)

        side = 880
        rectangle(side, 104, 336, 528, MAP_VIEW_PANEL)
        rectangle(side, 104, 336, 528, MAP_VIEW_EDGE, filled=False)
        self.font.draw(side + 24, 602, "다음 목표", MAP_VIEW_TEXT)
        if len(world.contract.stops) > 1:
            self.font.draw(side + 238, 602, f"{len(world.completed_stops)} / {len(world.contract.stops)}", MAP_VIEW_TEXT)
        next_bridge_stop = self.bridge_map_next_stop(world)
        if next_bridge_stop is not None:
            _, place, action = next_bridge_stop
            objective, target, accent = f"{place} {action}", "선택 지름길 · E 길게", ORANGE
        elif world.returning:
            objective, accent = "북쪽 안전지점 복귀", SAFE_GREEN
            target = "추격을 끊고 복귀" if world.return_blocked else "초록색 안전지점에 도착하면 완료"
        elif world.parcel == "waiting":
            objective, target, accent = "택배 수령", "주황색 수령지에서 E 길게", ORANGE
        else:
            objective, target, accent = "택배 전달", "붉은 원 배송지에서 E 길게", MAP_VIEW_TEXT
        self.font.draw(side + 24, 566, objective, accent)
        self.font.draw(side + 24, 532, target, MAP_VIEW_TEXT)
        p.draw_line(side + 24, 504, side + 312, 504, *MAP_VIEW_EDGE)
        self.font.draw(side + 24, 474, "지도 범례", MAP_VIEW_TEXT)
        for y, label, color, w, h, icon in (
            (435, "큰길", MAP_ROAD, 24, 9, None),
            (400, "골목", MAP_ALLEY, 24, 5, None),
            (365, "주택·건물", MAP_BUILDING, 25, 21, "west-house"),
            (330, "상점·정류장", MAP_LANDMARK, 25, 18, "shop"),
            (190, "차량", MAP_WRECK, 25, 12, "abandoned-car"),
        ):
            x, bottom = side + 36 - w / 2, y - h / 2
            if not self._draw_map_sprite(icon, x, bottom, w, h):
                rectangle(x, bottom, w, h, color)
            self.font.draw(side + 62, y, label, MAP_VIEW_TEXT)
        for y, label, color, pickup in ((260, "수령지", MAP_PICKUP, True), (225, "배송지", MAP_DROPOFF, False)):
            self.draw_map_pin(side + 36, y, color, pickup=pickup)
            self.font.draw(side + 62, y, label, MAP_VIEW_TEXT)
        if DELIVERY_CONTRACTS[1].stops[0] in world.contract.stops:
            gate_closed = world.gate is not None
            rectangle(side + 24, 153, 24, 4, MAP_CLOSED_GATE if gate_closed else MAP_OPEN_GATE)
            self.font.draw(side + 62, 155, "철문 · 닫힘" if gate_closed else "철문 · 열림", MAP_VIEW_TEXT)
        if world.contract.return_point is not None:
            self.draw_safe_map_marker(side + 36, 155, MAP_SAFE, backing=MAP_LABEL)
            self.font.draw(side + 62, 155, "안전지점", MAP_VIEW_TEXT)
        if world.shutter_wall is not None:
            color = MAP_CLOSED_GATE if world.shutter_closed else MAP_OPEN_GATE
            rectangle(side + 162, 188, 20, 4, color)
            status = "셔터 · 닫힘" if world.shutter_closed else "셔터 · 열림"
            self.font.draw(side + 191, 190, status, MAP_VIEW_TEXT)
        bridge = world.bridge_puzzle
        if bridge is not None:
            active = next_bridge_stop[0] if next_bridge_stop is not None else None
            self.draw_bridge_map_marker(side + 172, 435, "K", active=active == "K")
            status = "열쇠 수령" if bridge.has_key else "경비초소 · 열쇠"
            self.font.draw(side + 191, 435, status, ORANGE if active == "K" else MAP_VIEW_TEXT)
            self.draw_bridge_map_marker(side + 172, 400, "C", active=active == "C")
            self.font.draw(side + 191, 400, "관리실 · 회로", ORANGE if active == "C" else MAP_VIEW_TEXT)
            color = MAP_OPEN_GATE if bridge.bridge_down else MAP_CLOSED_GATE
            rectangle(side + 162, 363, 20, 4, color)
            status = "다리 지름길" if bridge.bridge_down else "다리 · 올라감"
            self.font.draw(side + 191, 365, status, SAFE_GREEN if bridge.bridge_down else MAP_VIEW_TEXT)
            if world.returning:
                self.font.draw(side + 191, 260, "동쪽 우회 가능", MAP_VIEW_TEXT)
                self.font.draw(side + 191, 236, "정류장길로 연결", MAP_VIEW_TEXT)
        self.draw_map_heading(side + 31, 295, 0)
        self.font.draw(side + 62, 295, "현재 위치·방향", MAP_VIEW_TEXT)
        self.draw_map_waypoint(side + 36, 120, 1)
        self.font.draw(side + 62, 120, "경유지", MAP_VIEW_TEXT)
        rectangle(64, 40, 29, 27, MAP_VIEW_PAPER)
        rectangle(64, 40, 29, 27, MAP_VIEW_EDGE, filled=False)
        self.font.draw(73, 54, "M", MAP_PAPER_INK)
        rectangle(101, 40, 43, 27, MAP_VIEW_PAPER)
        rectangle(101, 40, 43, 27, MAP_VIEW_EDGE, filled=False)
        self.font.draw(109, 54, "Esc", MAP_PAPER_INK)
        self.font.draw(156, 54, "닫기", MAP_VIEW_TEXT)
        self.font.draw(508, 54, "좌클릭 경유지 추가 · 우클릭 마지막 삭제", MAP_ROUTE_HINT)
        if world.waypoints:
            self.font.draw(508, 26, "Space 현재 경유지 건너뛰기", MAP_ROUTE_HINT)

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

    def wall(self, wall, outlines, beam_mask=None, *, glow_outline=(), opacity=1.0):
        x, y = self.project(wall.x, wall.y)
        height = wall_height(wall)
        ground_scale = self.ground_scale()
        depth = wall.depth * ground_scale
        if x >= WINDOW_WIDTH or x + wall.width <= 0 or y >= WINDOW_HEIGHT or y + height + depth <= 0:
            return

        textured = isinstance(wall, NeighborhoodWall)
        texture = WALL_TEXTURE_ALIASES.get(wall.texture, wall.texture) if textured else None
        image = self.neighborhood_walls.get(texture)
        oblique = image is not None and wall.oblique
        low_obstacle = image is not None and wall.texture in LOW_OBSTACLE_TEXTURES
        shutter = textured and wall.texture == "parking-shutter"
        long_shutter = shutter and wall.depth > wall.width
        # The shutter reuses the shorter iron gate's roof/front texture split.
        texture_height = 38 if shutter else height
        seam = (image.h - round(texture_height / 2)) / image.h if image is not None else 0.5
        if oblique:
            front, side, roof = house_planes(wall, x, y, ground_scale=ground_scale)
            foundation = quad(x, y, wall.width, depth + HOUSE_FOUNDATION_HEIGHT)
            for plane in (foundation, front, side, roof):
                self.draw_wall_plane(None, plane, 0, 1, (0, 0, 0), opacity=opacity)
        else:
            front = quad(x, y, wall.width, height)
            roof = quad(x, y + height, wall.width, depth)
            if low_obstacle:
                self.draw_wall_plane(image, front, seam, 1, (0, 0, 0), opacity=opacity)
                self.draw_wall_plane(image, roof, 0, seam, (0, 0, 0), opacity=opacity)
            else:
                self.draw_wall_plane(None, quad(x, y, wall.width, height + depth), 0, 1, (0, 0, 0), opacity=opacity)
        side_image = self.neighborhood_walls[f"{texture}-side"] if oblique else None

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
                    self.draw_wall_plane(image, front, seam, 1, facade_shade, (start, 0, end, 1), mask=mask,
                                         opacity=opacity)
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
                        self.draw_wall_plane(side_image, side, 0, 1, side_shade, (start, 0, end, 1), mask=mask,
                                             opacity=opacity)
                if low_obstacle and edge in ("left", "right"):
                    # Show the end of a low obstacle when approached along the lane.
                    band = side_band * min(1, (end - start) * 2)
                    bounds = (0, 0, band, 1) if edge == "left" else (1 - band, 0, 1, 1)
                    self.draw_wall_plane(image, front, seam, 1, facade_shade, bounds, mask=mask, opacity=opacity)
                if long_shutter and edge in ("left", "right"):
                    # The shutter opening follows the alley depth in the current projection.
                    face = quad(x, y, wall.width, height + depth)
                    self.draw_wall_plane(image, face, 0, 1, facade_shade, (0, start, 1, end),
                                         mask=mask, opacity=opacity)
                self.draw_wall_plane(image, roof, 0, seam, roof_shade, roof_bounds, alpha=roof_alpha, mask=mask,
                                     opacity=opacity)

    def draw_wall_plane(self, image, points, top, bottom, shade, bounds=(0, 0, 1, 1), *,
                        alpha=(255, 255, 255, 255), mask=None, opacity=1.0):
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
            vertex_alpha = (1 - t) * ((1 - s) * alpha[0] + s * alpha[1]) + t * (s * alpha[2] + (1 - s) * alpha[3])
            color = p.SDL_Color(*shade, round(opacity * vertex_alpha))
            vertices[i] = p.SDL_Vertex(p.SDL_FPoint(x, WINDOW_HEIGHT - y), color,
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

    def draw_shutter_entrance(self, shutter):
        x, y = self.project(shutter.x, shutter.y)
        depth = shutter.depth * self.ground_scale()

        def draw():
            if shutter.depth > shutter.width:
                for offset in range(3, int(depth), 12):
                    rectangle(x + (shutter.width - 4) / 2, y + offset, 4, 6, (178, 143, 73))
            else:
                for offset in range(3, int(shutter.width), 12):
                    rectangle(x + offset, y + (depth - 4) / 2, 6, 4, (178, 143, 73))

        self.draw_lit_region((x, y, shutter.width, depth), draw)

    def draw_shutter_control(self, position, *, closed):
        self.draw_control_box(position, "닫힘" if closed else "셔터", TEAL if closed else ORANGE)

    def draw_bridge_note_marker(self, position):
        x, y = self.project(*position)
        parts = ((-2, 0, 4, 29, (77, 61, 45)), (-13, 13, 26, 17, (117, 93, 64)),
                 (-9, 15, 18, 12, (209, 181, 127)), (-8, 26, 16, 3, (158, 128, 79)),
                 (-6, 22, 12, 1, (106, 80, 49)), (-6, 18, 8, 1, (116, 90, 57)))

        def draw(*, dimmed=False):
            for dx, dy, width, height, color in parts:
                rectangle(x + dx, y + dy, width, height, dim_color(color) if dimmed else color)

        bounds = (x - 13, y, 27, 31)
        glow_spans = self.glow_at_ground_depth(position, x)
        if glow_spans is not None:
            self.draw_lit_region(bounds, lambda: draw(dimmed=True), row_spans=glow_spans)
        self.draw_lit_region(bounds, draw)

    def draw_control_box(self, position, label, light_color, *, label_width=72):
        x, y = self.project(*position)

        def draw(*, dimmed=False):
            for left, bottom, width, height, color in (
                (x - 3, y, 6, 17, (77, 76, 69)),
                (x - 8, y + 17, 16, 15, (62, 77, 76)),
                (x - 5, y + 20, 10, 9, (107, 117, 104)),
                (x - 2, y + 23, 4, 4, light_color),
            ):
                rectangle(left, bottom, width, height, dim_color(color) if dimmed else color)

        bounds = (x - 8, y, 17, 33)
        glow_spans = self.glow_at_ground_depth(position, x)
        if glow_spans is not None:
            self.draw_lit_region(bounds, lambda: draw(dimmed=True), row_spans=glow_spans)
        self.draw_lit_region(bounds, draw)
        if self.light.contains(position):
            rectangle(x + 13, y + 20, label_width, 23, (16, 24, 28))
            self.font.draw(x + 19, y + 31, label, light_color)

    def draw_bridge_terrain(self, puzzle):
        x, y, width, depth = puzzle.channel_rect
        sx, sy = self.project(x, y)
        ground_scale = self.ground_scale()
        depth *= ground_scale
        parts = [(sx, sy, width, depth, (38, 58, 61)),
                 (sx, sy, width, 3, (94, 88, 74)),
                 (sx, sy + depth - 4, width, 4, (95, 99, 87))]
        for offset in range(6, width - 8, 14):
            parts.append((sx + offset, sy + 7 + (offset % 3) * 3, 8, 1, (78, 105, 105)))
        if puzzle.bridge_down:
            bx, by, bridge_width, bridge_depth = puzzle.bridge_rect
            left, bottom = self.project(bx, by)
            rise = bridge_depth * ground_scale
            parts.extend(((left, bottom, bridge_width, rise, (115, 111, 93)),
                          (left, bottom, 4, rise, (164, 142, 83)),
                          (left + bridge_width - 4, bottom, 4, rise, (164, 142, 83))))
            for rail in (5, 11, 17):
                parts.append((left + 5, bottom + rail, bridge_width - 10, 1, (69, 65, 54)))

        def draw(dimmed=False):
            for px, py, w, h, color in parts:
                rectangle(px, py, w, h, dim_color(color) if dimmed else color)

        bounds = (sx, sy, width, depth + 1)
        self.draw_lit_region(bounds, lambda: draw(dimmed=True),
                             row_spans=lambda row: self.glow_source[1].get(row, ()))
        self.draw_lit_region(bounds, draw)

    def draw_raised_bridge(self, wall):
        x, y = self.project(wall.x, wall.y)

        def draw(dimmed=False):
            parts = ((0, 0, wall.width, wall.height, (100, 96, 81)),
                     (0, wall.height - 5, wall.width, 5, (155, 133, 76)),
                     (0, 0, 4, wall.height, (137, 119, 77)),
                     (wall.width - 4, 0, 4, wall.height, (137, 119, 77)))
            for left, bottom, w, h, color in parts:
                rectangle(x + left, y + bottom, w, h, dim_color(color) if dimmed else color)
            for offset in range(8, wall.height - 6, 7):
                line = (58, 59, 54) if not dimmed else dim_color((58, 59, 54))
                rectangle(x + 4, y + offset, wall.width - 8, 2, line)

        def outline_columns(light):
            near = wall.y - .5 if light.origin[1] <= wall.y else wall.y + wall.depth + .5
            return light_depth_columns(light, near, x - wall.x)

        bounds = (x, y, wall.width + 1, wall.height + 1)
        glow_columns = outline_columns(self.glow_source[0])
        self.draw_lit_region(bounds, lambda: draw(dimmed=True), row_spans=lambda _: glow_columns)
        columns = merge_light_spans(span for light in self.light.lights for span in outline_columns(light))
        self.draw_lit_region(bounds, draw, row_spans=lambda _: columns)

    def draw_safe_zone(self, position, origin, walls, *, blocked):
        if math.dist(position, origin) > 150 or any(wall_blocks(origin, position, wall) for wall in walls):
            return
        x, y = position
        color = ORANGE if blocked else SAFE_GREEN
        ring = [(x + INTERACTION_RANGE * dx, y + INTERACTION_RANGE * dy) for dx, dy in PULSE_RING]
        visible = [not any(wall_blocks(origin, point, wall) for wall in walls) for point in ring]
        for i, (start, end) in enumerate(zip(ring, ring[1:])):
            if visible[i] and visible[i + 1]:
                p.draw_line(*self.project(*start), *self.project(*end), *color)
        self.draw_safe_map_marker(*self.project(*position), color)

    def draw_delivery_result(self):
        self.play_hud.draw_result(self.delivery)

    def draw_lit_zombie(self, zombie, combat, attack):
        x, y = self.project(zombie.x, zombie.y)
        ground_scale = self.ground_scale()
        bounds = self.combat_visual.zombie_rect(zombie, x, y)

        def draw():
            self.combat_visual.draw_zombie(zombie, x, y)

        position = zombie.x, zombie.y
        glow_spans = self.glow_at_ground_depth(position, x)
        if glow_spans is not None:
            opacity = zombie_glow_opacity(self.glow_source[0], position)
            if opacity:
                texture = self.combat_visual.zombie_texture(zombie)
                if p.SDL_SetTextureAlphaMod(texture, opacity) != 0:
                    raise RuntimeError(f"Nearby zombie opacity failed: {p.SDL_GetError()!r}")
                try:
                    self.draw_lit_region(bounds, draw, row_spans=lambda row: glow_spans(
                        zombie_light_row(row, y, ground_scale) if zombie.alive else row))
                finally:
                    p.SDL_SetTextureAlphaMod(texture, 255)

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
            sample = zombie_light_row(row, y, ground_scale) if zombie.alive else row
            return merge_light_spans(span for rows, columns in sources
                                     for span in clip_light_columns(rows.get(sample, ()), columns))

        self.draw_lit_region(bounds, draw, row_spans=zombie_row_spans)
        self.draw_zombie_markers(zombie, combat, attack, x, y, row_spans=zombie_row_spans)

    def draw_zombie_markers(self, zombie, combat, attack, x, y, *, row_spans=None):
        scale = self.combat_visual.display_scale
        if combat.result == "playing" and zombie.alive and zombie.state in ZOMBIE_MARKS:
            symbol, color = ZOMBIE_MARKS[zombie.state]
            left, bottom = x + 24 * scale, y + 96 * scale

            def draw_status():
                rectangle(left, bottom, 18, 18, (16, 24, 28))
                self.font.draw(left + 4, bottom + 9, symbol, color)

            self.draw_lit_region((left, bottom - 2, 19, 23), draw_status, row_spans=row_spans)
        if attack is None or not any(target is zombie for target in attack.hit_targets):
            return
        elapsed = attack.elapsed - attack.hit_time
        if not 0.0 <= elapsed < HIT_MARK_DURATION:
            return
        progress = elapsed / HIT_MARK_DURATION
        alpha = round(255 * min(1.0, (1.0 - progress) / .8) ** 2)
        spread = round(3 * progress)
        away_x, away_y = math.cos(attack.angle), math.sin(attack.angle)
        # Keep the spark above the courier's silhouette when the target is behind it.
        height = 57 + 39 * max(0, away_y) if zombie.alive else 18
        x = round(x + 8 * scale * away_x)
        y = round(y + scale * height)

        def draw_hit():
            highlight = (*WHITE, alpha)
            gold = (*ORANGE, alpha)
            p.draw_line(x - 10 - spread, y + 4 + spread, x - 4 - spread, y + 2 + spread, *gold)
            p.draw_line(x - 2 - spread, y + 5 + spread, x - 3 - spread, y + 9 + spread, *highlight)
            p.draw_line(x + 4 + spread, y + 3 + spread, x + 9 + spread, y + 6 + spread, *gold)
            p.draw_line(x + 4 + spread, y - 2 - spread, x + 8 + spread, y - 4 - spread, *highlight)
            if progress < .45:
                p.draw_rectangle(x - 1, y - 1, x + 1, y + 1, *highlight, filled=True)

        self.draw_lit_region((x - 13, y - 7, 27, 20), draw_hit, row_spans=row_spans)

    def draw(self, player, walls, target, focused=True):
        self._draw_scene(player, walls, target, focused)
        bridge = self.delivery.bridge_puzzle if self.delivery is not None else None
        if self.bridge_note_open:
            self.play_hud.draw_bridge_note()
        elif bridge is not None and bridge.panel_open:
            self.play_hud.draw_bridge_panel(bridge)
        elif self.abandon_confirmation:
            self.play_hud.draw_abandon_confirmation()

    def draw_defeat(self, player, walls, target, elapsed, attacker):
        if target is None:
            target = player.x + math.cos(player.aim_angle), player.y + math.sin(player.aim_angle)
        self._draw_scene(player, walls, target, True, defeat_elapsed=elapsed, defeat_attacker=attacker)

    def _draw_scene(self, player, walls, target, focused, *, defeat_elapsed=None, defeat_attacker=None):
        if self.choosing_delivery:
            self.draw_delivery_selection()
            return
        if self.map_open:
            self.draw_map(player)
            return
        aim = self.cursor_world(self.cursor) if self.cursor is not None else target
        self._draw_world(player, walls, aim, defeat_elapsed, defeat_attacker)
        self._draw_overlay(player, target, aim, focused, defeat_elapsed)

    def _draw_world(self, player, walls, aim, defeat_elapsed, defeat_attacker):
        p.SDL_SetRenderDrawColor(p.renderer, 0, 0, 0, 255)
        p.SDL_RenderClear(p.renderer)
        origin = (player.x, player.y)
        world_size = self.combat.world_size if self.combat is not None else (WORLD_WIDTH, WORLD_HEIGHT)
        beam, *lamps = self.prepare_light(player, walls, aim).lights
        glow = self.nearby_light
        glow_outline = glow.outline()
        glow_walls = {id(wall) for wall in glow.walls}
        # Station labels and status marks remain reserved for strong lighting.
        self.glow_source = (glow, light_source_rows(glow, self.project))
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
        self.draw_ground_light(glow, glow_outline, NEARBY_GLOW_COLOR, (0, 0, 0), feathered=True)
        self.draw_ground_light(beam, beam_outline, (28, 26, 23), (104, 84, 53), feathered=True)
        self.draw_streetlight_pools(lamps, lamp_outlines)
        delivery = self.delivery
        bridge = delivery.bridge_puzzle if delivery is not None else None
        defeated = delivery is not None and delivery.result == "defeated"
        if bridge is not None:
            self.draw_bridge_terrain(bridge)
        outlines = (beam_outline, *lamp_outlines)
        self.draw_noise_pulse(self.sprint_pulse, self.sprint_pulse_remaining, TEAL)
        self.draw_noise_pulse(self.bottle_pulse, self.bottle_pulse_remaining, ORANGE)
        self.draw_noise_pulse(self.vehicle_alarm, self.vehicle_alarm_remaining, ORANGE,
                              duration=VEHICLE_ALARM_DURATION)
        foot = self.project(*origin)
        combat = getattr(self, "combat", None)
        attack = combat.attack if combat is not None else None
        courier_style = {"empty_handed": delivery.parcel != "carrying"} if delivery is not None else {}
        bottles = []
        stations = ()
        if delivery is not None:
            stations = ((delivery.pickup,) if delivery.parcel == "waiting"
                        else tuple(stop.position for stop in delivery.remaining_stops))
            if delivery.returning or (bridge is not None and defeated and delivery.parcel == "delivered"):
                if not defeated:
                    self.draw_safe_zone(delivery.contract.return_point, origin, walls, blocked=delivery.return_blocked)
                if delivery.shutter_position is not None:
                    stations = (*stations, delivery.shutter_position)
                    if not delivery.shutter_closed:
                        self.draw_shutter_entrance(delivery.shutter_wall)
                if bridge is not None:
                    stations = (*stations, bridge.key_position, bridge.panel_position)
                    if delivery.returning:
                        stations = (*stations, bridge.note_position)
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
                if actor == delivery.shutter_position:
                    self.draw_shutter_control(actor, closed=delivery.shutter_closed)
                elif bridge is not None and actor == bridge.key_position:
                    self.draw_control_box(actor, "경비초소", TEAL if bridge.has_key else ORANGE,
                                          label_width=88)
                elif bridge is not None and actor == bridge.panel_position:
                    self.draw_control_box(actor, "관리실", TEAL if bridge.bridge_down else ORANGE)
                elif bridge is not None and actor == bridge.note_position:
                    self.draw_bridge_note_marker(actor)
                else:
                    self.draw_station(actor, delivery.parcel == "waiting")
            elif kind == "lamp":
                self.draw_lit_prop(actor, self.streetlamp_image)
            elif kind == "wall":
                texture = getattr(actor, "texture", None)
                if texture in BRIDGE_TERRAIN:
                    if texture == "bridge-raised":
                        self.draw_raised_bridge(actor)
                    continue
                opacity = self.building_opacity(actor)
                if opacity > 0.0:
                    self.wall(actor, outlines, beam_mask, glow_outline=glow_outline if id(actor) in glow_walls else (),
                              opacity=opacity)
            elif kind == "zombie":
                if defeat_attacker is not None and actor is defeat_attacker[0]:
                    actor = defeat_attacker[1]
                self.draw_lit_zombie(actor, combat, attack)
            else:
                if defeated:
                    attacker = delivery.fatal_zombie_strike
                    fall_x = player.x - attacker[0].x if attacker else -math.cos(player.aim_angle)
                    progress = 1.0 if defeat_elapsed is None else opening.courier_fall_progress(defeat_elapsed)
                    fall_angle = math.copysign(math.radians(83) * progress, -fall_x)
                    self.player_visual.draw(*foot, fall_angle=fall_angle, **courier_style)
                elif combat is None or not self.combat_visual.draw_attack(
                        combat.attack, *foot, walk_frame_index=self.player_visual.frame_index, **courier_style):
                    self.player_visual.draw(*foot, **courier_style)
                if not defeated:
                    cross(*foot, TEAL, size=4)

    def _draw_overlay(self, player, target, aim, focused, defeat_elapsed):
        delivery = self.delivery
        if delivery is not None and delivery.result == "defeated":
            if defeat_elapsed is None:
                p.SDL_SetRenderDrawColor(p.renderer, 4, 7, 10, 175)
                p.SDL_RenderFillRect(p.renderer, None)
                self.draw_delivery_result()
            return
        # The cursor stays at its screen position while the world shakes.
        target_screen = (world_to_screen(*target, self.camera, ground_scale=self.ground_scale()) if self.cursor is None
                         else (self.cursor[0], WINDOW_HEIGHT - 1 - self.cursor[1]))
        cross(*target_screen, ORANGE, size=7)
        origin = (player.x, player.y)
        foot = self.project(*origin)
        combat = self.combat
        attack = combat.attack if combat is not None else None
        angle = attack.angle if attack is not None else player.aim_angle
        desired = math.atan2(target[1] - player.y, target[0] - player.x)
        if abs(math.remainder(desired - angle, math.tau)) > math.radians(5):
            tip = self.project(player.x + 27 * math.cos(angle), player.y + 27 * math.sin(angle))
            p.draw_line(*foot, *tip, *TEAL)
            cross(*tip, TEAL, size=2)
        if delivery is not None:
            if delivery.result == "playing":
                if (focused and not self.bridge_note_open and not self.abandon_confirmation
                        and delivery.can_read_bridge_note()):
                    x, y = self.project(*delivery.bridge_puzzle.note_position)
                    rectangle(x - 70, y + 81, 140, 26, (23, 25, 24))
                    rectangle(x - 70, y + 81, 140, 26, (137, 110, 67), filled=False)
                    self.font.draw(x - 55, y + 94, "E  쪽지 읽기", (239, 218, 172))
                near_visible_zombie = False
                if focused and self.play_hud.watch_for_sneak_hint(delivery):
                    for zombie in delivery.zombies:
                        position = zombie.x, zombie.y
                        if (zombie.alive and math.dist(origin, position) <= SNEAK_HINT_RANGE
                                and (self.light.contains(position) or self.nearby_light.contains(position))
                                and delivery._player_line_clear(zombie)):
                            near_visible_zombie = True
                            break
                waypoint_direction = None
                if delivery.waypoints:
                    waypoint_x, waypoint_y = self.project(*delivery.waypoints[0])
                    waypoint_direction = (waypoint_x - foot[0], foot[1] - waypoint_y)
                self.play_hud.draw(delivery, self.light, aim, focused=focused,
                                   alarm=self.vehicle_alarm_remaining > 0, near_visible_zombie=near_visible_zombie,
                                   waypoint_direction=waypoint_direction)
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


def play_ending(renderer, art, world, audio, *, player_hit, target=None):
    delivered = world.result == "delivered"
    duration = opening.ENDING_DURATION if delivered else opening.FAILURE_DURATION
    attacker = None
    if not delivered and world.fatal_zombie_strike is not None:
        source, strike = world.fatal_zombie_strike
        pose = renderer.combat_visual._motion_for(source)
        visual_strike = replace(strike, facing=pose.attack_facing or strike.facing)
        attacker = source, replace(source, attack=visual_strike)
    start = time.perf_counter()
    previous = 0.0
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
            if delivered:
                opening.draw_ending(elapsed, renderer.font, art, world)
            else:
                renderer.update_shake((elapsed - previous) * opening.FAILURE_MOTION_RATE)
                if attacker is not None:
                    visual_strike.elapsed = min(math.nextafter(strike.duration, 0.0),
                                                strike.elapsed + elapsed * opening.FAILURE_MOTION_RATE)
                renderer.draw_defeat(world.player, world.walls, target, elapsed, attacker)
                opening.draw_defeat_overlay(elapsed, renderer.font, art)
                previous = elapsed
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
            audio_dir = BASE_DIR / "assets/audio"
            music = BackgroundMusic(audio_dir / "night-delivery-loop.ogg", layers=(
                audio_dir / "night-threat-layer.ogg", audio_dir / "night-chase-layer.ogg",
            ))
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
            map_toggled = False
            note_close_requested = False
            waypoint_actions = []
            abandon_requested = False
            abandon_decision = None
            bridge = world.bridge_puzzle if delivery_run else None
            circuit_keys = []
            for event in poll_events():
                if event.type == p.SDL_QUIT:
                    running = False
                elif renderer.bridge_note_open:
                    if event.type == p.SDL_KEYDOWN and not event.key.repeat:
                        if event.key.keysym.sym in (p.SDLK_e, p.SDLK_ESCAPE):
                            note_close_requested = True
                    elif (event.type == p.SDL_WINDOWEVENT
                          and event.window.event == p.SDL_WINDOWEVENT_FOCUS_LOST):
                        lost_focus = True
                elif bridge is not None and bridge.panel_open:
                    if event.type == p.SDL_KEYDOWN and not event.key.repeat:
                        circuit_keys.append(event.key.keysym.sym)
                    elif (event.type == p.SDL_WINDOWEVENT
                          and event.window.event == p.SDL_WINDOWEVENT_FOCUS_LOST):
                        lost_focus = True
                elif renderer.abandon_confirmation or abandon_requested:
                    if (renderer.abandon_confirmation and abandon_decision is None
                            and event.type == p.SDL_KEYDOWN and not event.key.repeat):
                        key = event.key.keysym.sym
                        if key in (p.SDLK_RETURN, p.SDLK_KP_ENTER, p.SDLK_ESCAPE):
                            abandon_decision = key != p.SDLK_ESCAPE
                    elif (event.type == p.SDL_WINDOWEVENT
                          and event.window.event == p.SDL_WINDOWEVENT_FOCUS_LOST):
                        lost_focus = True
                elif event.type == p.SDL_KEYDOWN and not event.key.repeat:
                    key = event.key.keysym.sym
                    if key == p.SDLK_ESCAPE:
                        if renderer.map_open or (delivery_run and world.result == "playing" and map_toggle):
                            map_toggle = renderer.map_open
                        else:
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
                    elif (key == p.SDLK_SPACE and delivery_run and world.result == "playing"
                          and renderer.map_open != map_toggle):
                        waypoint_actions.append(("skip", None))
                    elif (delivery_run and world.result != "playing"
                          and key in (p.SDLK_RETURN, p.SDLK_KP_ENTER)):
                        retry_requested = True
                    pressed.add(key)
                    if key == p.SDLK_r:
                        if delivery_run and world.result == "playing":
                            abandon_requested = True
                        else:
                            reset_requested = True
                elif event.type == p.SDL_KEYUP and not event.key.repeat:
                    pressed.discard(event.key.keysym.sym)
                elif event.type == p.SDL_MOUSEMOTION:
                    cursor = (event.motion.x, event.motion.y)
                elif event.type == p.SDL_MOUSEBUTTONDOWN:
                    cursor = (event.button.x, event.button.y)
                    button = event.button.button
                    if (delivery_run and not renderer.choosing_delivery and world.result == "playing"
                            and renderer.map_open != map_toggle):
                        if button == p.SDL_BUTTON_LEFT:
                            waypoint_actions.append(("add", cursor))
                        elif button == p.SDL_BUTTON_RIGHT:
                            waypoint_actions.append(("remove", None))
                    elif button == p.SDL_BUTTON_LEFT:
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
            motor_sound = None
            if focused and not lost_focus and bridge is not None and bridge.panel_open:
                for key in circuit_keys:
                    if key == p.SDLK_ESCAPE:
                        world.close_bridge_panel()
                        break
                    index = DELIVERY_KEYS.get(key, -1)
                    if 0 <= index < 3 and world.rotate_bridge_tile(index):
                        motor_sound = bridge.bridge_position
                        renderer.reset_streetlights()
                        renderer.light = None
                        break
            confirmation_changed = focused and not lost_focus and (abandon_requested or abandon_decision is not None)
            if confirmation_changed:
                renderer.abandon_confirmation = abandon_requested
                reset_requested = abandon_decision is True
                pressed.clear()
                pending_click = pending_interact = mouse_held = False
                pending_bottle_pickup = pending_bottle_throw = False
                map_toggle = False
                waypoint_actions.clear()
            if reset_requested or retry_requested or contract_choice is not None:
                if contract_choice is not None:
                    world.select_contract(contract_choice)
                    if music is not None:
                        music.start()
                else:
                    world.reset()
                if music is not None:
                    music.reset()
                renderer.choosing_delivery = delivery_run and reset_requested
                if delivery_run:
                    renderer.reset_streetlights()
                    renderer.reset_building_fades()
                    renderer.play_hud.reset_delivery()
                player, walls = world.player, world.walls
                renderer.follow(player)
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
                renderer.bridge_note_open = False
                renderer.update_shake(math.inf)
                renderer.update_sprint_pulse(math.inf)
                renderer.update_bottle_pulse(math.inf)
                renderer.update_vehicle_alarm(math.inf)
                target = world.pickup if delivery_run else (world.zombie.x, world.zombie.y)
                aim_player(player, *target)
            elif map_toggle and focused and not lost_focus and delivery_run and world.result == "playing":
                renderer.map_open = not renderer.map_open
                map_toggled = True
                if renderer.map_open and world.parcel == "carrying":
                    renderer.play_hud.dismiss_hint("M")
                pressed.clear()
                pending_click = pending_interact = mouse_held = False
                pending_bottle_pickup = pending_bottle_throw = False
            if focused and not lost_focus and not reset_requested:
                for action, map_cursor in waypoint_actions:
                    if action == "skip":
                        world.skip_waypoint()
                    elif action == "remove":
                        world.remove_last_waypoint()
                    elif (point := renderer.map_world_at(*map_cursor)) is not None:
                        world.add_waypoint(point)
            if renderer.choosing_delivery:
                if music is not None:
                    music.update(dt, focused=False)
                if zombie_audio is not None:
                    zombie_audio.update(dt, distance=None, stride=0.0, active=False)
                renderer.draw(player, walls, target, focused)
                p.update_canvas()
                continue
            active = (focused and not lost_focus and not renderer.map_open
                      and not renderer.abandon_confirmation and not confirmation_changed and not renderer.bridge_note_open
                      and (bridge is None or not bridge.panel_open)
                      and contract_choice is None and not retry_requested)
            note_opened = (active and not map_toggled and pending_interact and delivery_run
                           and world.can_read_bridge_note())
            note_closed = note_close_requested and focused and not lost_focus
            if note_opened or note_closed:
                renderer.bridge_note_open = note_opened
                pressed.clear()
                mouse_held = False
                active = False
            if not delivery_run and cursor is not None:
                light = renderer.light
                if light is None:
                    aim = (player.x, player.y)
                    light = renderer.prepare_light(player, walls, aim)
                target = mouse_target(world, renderer.combat_visual, *cursor, light, renderer.camera,
                                      renderer.shake_offset, wall_alpha=renderer.wall_alpha,
                                      nearby_light=renderer.nearby_light)
            axis_x = int(p.SDLK_d in pressed) - int(p.SDLK_a in pressed)
            axis_y = int(p.SDLK_w in pressed) - int(p.SDLK_s in pressed)
            motion = renderer.player_visual.locomotion
            facing_hint = motion.facing if motion._initialized else None
            was_playing = world.result == "playing"
            swing_started = False
            if pending_click and active:
                facing = select_facing(player.aim_angle, facing_hint)
                swing_started = world.start_attack(facing=facing, stationary_front_right=True)
            bottle_picked_up = delivery_run and active and pending_bottle_pickup and world.pick_up_bottle()
            bottle_thrown = False
            if delivery_run and active and pending_bottle_throw:
                throw_target = renderer.cursor_world(cursor) if cursor is not None else target
                bottle_thrown = world.throw_bottle(throw_target)
            before = (player.x, player.y)
            zombie_origins = [(zombie.x, zombie.y) for zombie in world.zombies]
            strike = world.attack
            strike_elapsed = strike.elapsed if strike is not None else 0.0
            was_landed = strike is not None and strike.landed
            hp_before = world.player_hp
            sprint = p.SDLK_LSHIFT in pressed or p.SDLK_RSHIFT in pressed
            sneak = p.SDLK_LCTRL in pressed or p.SDLK_RCTRL in pressed
            world.update(dt if active else 0.0, axis_x, axis_y, facing_hint=facing_hint, sprint=sprint, sneak=sneak)
            if delivery_run and active:
                world.advance_waypoint()
            dx, dy = player.x - before[0], player.y - before[1]
            player_hit = world.player_hp < hp_before
            bottle_impact = world.bottle_impact if delivery_run and active else None
            renderer.update_bottle_pulse(dt if active else math.inf, bottle_impact)
            door_sound = None
            parcel_picked_up = parcel_dropped = False
            if delivery_run:
                gate_was_closed = world.gate is not None
                shutter_was_closed = world.shutter_closed
                was_waiting = world.parcel == "waiting"
                stops_before = len(world.completed_stops)
                completed = world.update_interaction(
                    dt if active else 0.0, held=active and p.SDLK_e in pressed,
                    pressed=active and pending_interact, moving=player.moved, damaged=player_hit,
                )
                if completed and world.just_unlocked_two_stop:
                    save_two_stop_unlock()
                if completed and bridge is not None and bridge.panel_open:
                    pressed.clear()
                    mouse_held = False
                gate_opened = completed and gate_was_closed and world.gate is None
                shutter_closed = completed and not shutter_was_closed and world.shutter_closed
                parcel_picked_up = completed and was_waiting and world.parcel == "carrying"
                parcel_dropped = (completed and len(world.completed_stops) > stops_before
                                  and world.result == "playing")
                if gate_opened or shutter_closed:
                    door_sound = world.gate_position if gate_opened else world.shutter_position
                    renderer.reset_streetlights()
                    renderer.light = None
            ending = delivery_run and was_playing and world.result in ("delivered", "defeated")
            audio_active = active and not reset_requested
            hearing_active = audio_active and world.result == "playing"
            renderer.update_sprint_pulse(dt if hearing_active else math.inf,
                                         world.sprint_step if hearing_active else None)
            vehicle_alarm = world.vehicle_alarm if delivery_run and hearing_active else None
            vehicle_hit = world.vehicle_hit if delivery_run and hearing_active else None
            renderer.update_vehicle_alarm(dt if hearing_active else math.inf, vehicle_alarm)
            swing_sound_due = swing_started
            if strike is not None and strike.stationary_front_right and FRONT_RIGHT_SWING_SOUND_DELAY > 0.0:
                # Use the combat clock so pausing or resetting cannot leave a queued sound.
                cue_time = FRONT_RIGHT_SWING_SOUND_DELAY - 1e-9
                swing_sound_due = strike is world.attack and strike_elapsed < cue_time <= strike.elapsed
            strike_landed = strike is not None and strike.landed and not was_landed
            heavy_hit = strike_landed and (len(strike.hit_targets) > 1
                                           or any(not zombie.alive for zombie in strike.hit_targets))
            strength = 0
            hit_angle = None
            if player_hit:
                strength = 4
            elif strike_landed:
                strength = 5 if delivery_run and heavy_hit else 3
                if delivery_run:
                    hit_angle = strike.angle
            renderer.update_shake(dt if active and not reset_requested else math.inf, strength, hit_angle=hit_angle)
            distance = None
            nearest_zombie = None
            stride = pan = 0.0
            chasing = False
            listener = (player.x, player.y)
            patrol_step = None
            heavy_step = None
            listening_at_corner = (delivery_run and hearing_active
                                   and math.dist(listener, REAR_ALLEY_LISTEN_POINT) <= REAR_ALLEY_LISTEN_RADIUS)
            for zombie, (x, y) in zip(world.zombies, zombie_origins):
                zombie_dx, zombie_dy = zombie.x - x, zombie.y - y
                renderer.combat_visual.update_zombie(zombie, zombie_dx, zombie_dy, paused=not active)
                if zombie.alive:
                    chasing |= zombie.state == "chase"
                    source = (zombie.x, zombie.y)
                    enemy_distance, enemy_pan = sound_position(listener, source)
                    recoil_x, recoil_y = zombie.recoil_offset
                    enemy_stride = math.hypot(zombie_dx - recoil_x, zombie_dy - recoil_y)
                    if listening_at_corner and zombie.state == "patrol" and zombie.patrol_points:
                        patrol_step = PatrolFootstep(enemy_distance, enemy_stride, enemy_pan,
                                                     any(wall_blocks(listener, source, wall) for wall in walls))
                    if zombie.appearance == HEAVY_ZOMBIE_APPEARANCE:
                        if hearing_active:
                            heavy_step = HeavyFootstep(enemy_distance, enemy_stride, enemy_pan,
                                                       any(wall_blocks(listener, source, wall) for wall in walls))
                        continue
                    if distance is None or enemy_distance < distance:
                        distance = enemy_distance
                        pan = enemy_pan
                        nearest_zombie = zombie
                        stride = enemy_stride
            if music is not None:
                if delivery_run:
                    playing = active and world.result == "playing"
                    threat_distance = distance
                    if heavy_step is not None:
                        threat_distance = min(heavy_step.distance, distance) if distance is not None else heavy_step.distance
                    music.update(dt, distance=threat_distance, focused=playing, chasing=playing and chasing)
                else:
                    music.update(dt, distance=distance, focused=active)
            if zombie_audio is not None and not ending:
                occluded = hearing_active and nearest_zombie is not None and any(
                    wall_blocks(listener, (nearest_zombie.x, nearest_zombie.y), wall)
                    for wall in walls)
                preserve_map_cue = (renderer.map_open or renderer.bridge_note_open) and focused and not lost_focus
                zombie_audio.update(dt, distance=distance if hearing_active else None, stride=stride, active=audio_active,
                                    occluded=occluded, preserve_map_cue=preserve_map_cue,
                                    pan=pan if hearing_active else 0.0, patrol_step=patrol_step, heavy_step=heavy_step)
                if map_toggled or note_opened or note_closed:
                    zombie_audio.play_map_toggle()
                if bottle_picked_up:
                    zombie_audio.play_bottle_pickup()
                if bottle_thrown:
                    zombie_audio.play_bottle_throw()
                if parcel_picked_up:
                    zombie_audio.play_parcel_pickup()
                if parcel_dropped:
                    zombie_audio.play_parcel_drop()
                if audio_active and swing_sound_due:
                    zombie_audio.play_bat_swing()
                if strike_landed:
                    heavy_impact = heavy_hit or any(zombie.appearance == HEAVY_ZOMBIE_APPEARANCE
                                                    for zombie in strike.hit_targets)
                    zombie_audio.play_zombie_hit(heavy=heavy_impact)
                if player_hit:
                    zombie_audio.play_player_hit()
                if bottle_impact is not None:
                    sound_distance, sound_pan = sound_position(listener, bottle_impact)
                    zombie_audio.play_bottle_break(sound_distance, pan=sound_pan)
                if door_sound is not None:
                    sound_distance, sound_pan = sound_position(listener, door_sound)
                    zombie_audio.play_gate_open(sound_distance, pan=sound_pan)
                if motor_sound is not None:
                    sound_distance, sound_pan = sound_position(listener, motor_sound)
                    zombie_audio.play_bridge_motor(sound_distance, pan=sound_pan)
                if vehicle_hit is not None:
                    sound_distance, sound_pan = sound_position(listener, vehicle_hit)
                    zombie_audio.play_vehicle_hit(sound_distance, pan=sound_pan)
                if vehicle_alarm is not None:
                    sound_distance, sound_pan = sound_position(listener, world.vehicle_alarm_source)
                    zombie_audio.play_vehicle_alarm(sound_distance, pan=sound_pan)
                if hearing_active:
                    zombie_audio.update_player_steps(math.hypot(dx, dy), sprinting=world.sprinting,
                                                    sneaking=world.sneaking)
            if smoke_test:
                name, player.x, player.y = smoke_poses[frame]
            if active and world.result == "playing":
                renderer.follow(player, dt, cursor=cursor)
                if delivery_run:
                    renderer.update_building_fades(player, walls, dt)
            renderer.cursor = cursor
            if delivery_run and cursor is not None and not renderer.map_open:
                aim = renderer.cursor_world(cursor)
                light = renderer.prepare_light(player, walls, aim)
                target = mouse_target(world, renderer.combat_visual, *cursor, light, renderer.camera,
                                      renderer.shake_offset, wall_alpha=renderer.wall_alpha,
                                      building_opacity=renderer.building_opacity, nearby_light=renderer.nearby_light,
                                      ground_scale=renderer.ground_scale())
            if active and strike is None and world.result == "playing":
                aim_player(player, *target, max_turn=TURN_SPEED * dt)
            display_angle = world.attack.angle if world.attack is not None else player.aim_angle
            renderer.player_visual.update(display_angle, dx, dy, sprinting=delivery_run and world.sprinting)
            if ending:
                if not play_ending(renderer, cutscene_art, world, zombie_audio, player_hit=player_hit, target=target):
                    return
                pressed.clear()
                mouse_held = False
                cursor = current_cursor()
                renderer.cursor = cursor
                if world.result == "defeated":
                    renderer.update_shake(math.inf)
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
