"""Dead Route alley delivery, combat and flashlight rendering."""
from __future__ import annotations

import argparse
import ctypes
from dataclasses import replace
import math
from pathlib import Path
import time

import pico2d.pico2d as p

import display
from core import WORLD_WIDTH, WORLD_HEIGHT, aim_player, wall_blocks
from combat import CombatWorld, HEAVY_ZOMBIE_APPEARANCE, MAX_STAMINA
from combat_visual import CombatVisual
from contract_selection import contract_card_at, contract_dispatch_at, draw_contract_selection, load_contract_previews
from delivery import (BUS_STOP, DELIVERY_CONTRACTS, FRONT_HOME_STOP, INTERACTION_RANGE, MANAGEMENT_STOP,
                      PLAYABLE_CONTRACTS, REAR_ALLEY_LISTEN_POINT, REAR_HOME_STOP, SHOP_STOP,
                      TOWN_BASE_WALLS, TOWN_ROADS, TOWN_SIZE, DeliveryWorld, NeighborhoodWall)
from delivery_audio_state import DeliveryAudioState, EnemyAcoustics, ZOMBIE_HEARING_DISTANCE, select_footstep_sources
from flashlight import Flashlight, LightField, feathered_beam_mesh, nearby_glow, nearby_glow_strength
from locomotion import Locomotion, select_facing
from play_hud import INTERACTION_LABELS, PAUSE_MENU, PlayHUD, SAFE_GREEN, SMALL as HUD_SMALL
from player_visual import PlayerVisual, load_atlas
from spatial_audio import AudioSettings, ZombieAudio, ZombieFootstep
from town_map_art import MAP_ICON_ATLAS_SIZE, MAP_ICON_CLIPS
from town_map_art import draw_base as draw_map_base, place_label as place_map_label
from truck_sequence import TruckVisual, courier_step, pickup_facing, pickup_frame, truck_bounds
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
RETURN_PERSPECTIVE_STRENGTH = .06
WALL_HEIGHT = 110
DELIVERY_CHARACTER_SCALE = 0.60
CONTRACT_NUMBERS = tuple(PLAYABLE_CONTRACTS)
NUMBER_KEYS = {p.SDLK_1: 1, p.SDLK_KP_1: 1, p.SDLK_2: 2, p.SDLK_KP_2: 2,
               p.SDLK_3: 3, p.SDLK_KP_3: 3, p.SDLK_4: 4, p.SDLK_KP_4: 4}
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
BUILDING_ROOF_LIGHT_BAND = 36
GROUND_NEUTRAL = 144
STREETLIGHT_RADIUS = 185.0
BEAM_GROUND_EDGE = (50, 46, 37)
BEAM_GROUND_FALLOFF = (89, 75, 60)
NEARBY_GLOW_COLOR = (132, 118, 99)
NEARBY_GLOW_TINT = 84
ZOMBIE_GLOW_BODY_PAD = 12.0
ZOMBIE_LIGHT_DEPTH_SCALE = 0.35
TRASH_CAN_POSITION = (365.0, 300.0)
WHITE = (231, 236, 231)
TEAL = (86, 225, 194)
ORANGE = (255, 182, 78)
MAP_INK = (14, 20, 23)
MAP_BORDER = (91, 112, 112)
MAP_CLOSED_GATE = (204, 150, 104)
MAP_OPEN_GATE = (122, 188, 153)
MAP_PAPER_INK = (54, 57, 47)
MAP_LABEL = (249, 236, 203)
MAP_LABEL_EDGE = (163, 137, 100)
MAP_ROUTE_INK = (36, 73, 127)
MAP_ROUTE_HINT = (176, 205, 245)
MAP_PLAYER = (67, 168, 255)
MAP_PLAYER_INK = (19, 73, 130)
MAP_PLAYER_RADIUS = 14
PUZZLE_DOT = (255, 211, 72)
PUZZLE_MARKER_DISTANCE = 210.0
MAP_ROAD_INK = (91, 75, 46)
MAP_ALLEY_INK = (100, 96, 81)
MAP_PICKUP = (168, 85, 27)
MAP_DROPOFF = (172, 48, 39)
MAP_SAFE = (36, 110, 61)
MAP_COMPLETED = (108, 114, 103)
MAP_DETOUR = (22, 104, 94)
MAP_VIEW_BG = (27, 23, 19)
MAP_VIEW_PANEL = (49, 39, 31)
MAP_VIEW_EDGE = (138, 111, 79)
MAP_VIEW_PAPER = (227, 211, 178)
MAP_VIEW_TEXT = (243, 228, 201)
MAP_VIEW_MUTED = (170, 158, 140)
PLAY_MAP_VIEWPORT = (64, 104, 792, 528)
TRUCK_MAP_AREA = (1440, 650, 3440, 2000)
MAP_VIEW_BUTTON = (700, 657, 206, 34)
HIT_MARK_DURATION = 0.14
STATIONARY_SWING_SOUND_DELAY = 0.060
NOISE_PULSE_DURATION = 0.24
VEHICLE_ALARM_DURATION = 1.2
AUDIO_PAN_NEAR_RADIUS = 72.0
REAR_ALLEY_LISTEN_RADIUS = 65.0
PULSE_RING = tuple((math.cos(i * math.tau / 24), math.sin(i * math.tau / 24)) for i in range(25))
ZOMBIE_MARKS = {"chase": ("!", ORANGE), "investigate": ("?", TEAL), "search": ("?", TEAL)}
PAUSE_VOLUME_FIELDS = ("master", "music", "effects")
PAUSE_VOLUME_STEP = 10
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
    logical_x, logical_y = ctypes.c_float(), ctypes.c_float()
    p.SDL_RenderWindowToLogical(p.renderer, x.value, y.value, ctypes.byref(logical_x), ctypes.byref(logical_y))
    return display.cursor_in_canvas(logical_x.value, logical_y.value)


def sorted_drawables(player, walls, zombie=None, *, zombies=(), prop=None, stations=(), lamps=(), street_props=(),
                     bottles=(), truck=None):
    # Stable ties: fixed props precede walls and characters at the same ground y.
    objects = [("prop", prop)] if prop is not None else []
    objects.extend(("station", position) for position in stations)
    objects.extend(("lamp", position) for position in lamps)
    objects.extend(("street-prop", decoration) for decoration in street_props)
    objects.extend(("bottle", bottle) for bottle in bottles)
    if truck is not None:
        objects.append(("truck", truck))
    objects.extend(("wall", wall) for wall in walls)
    if zombie is not None:
        objects.append(("zombie", zombie))
    objects.extend(("zombie", enemy) for enemy in zombies)
    objects.append(("player", player))
    return sorted(objects, key=lambda item: -(item[1][1] if item[0] in ("prop", "station", "lamp", "bottle", "truck")
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
                       and any(left <= world_x < right for left, right in source.open_light.spans_at(depth))
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


def puzzle_markers(world):
    """Return available devices for both the map and world. Gates own their line-of-sight blocker."""
    if not world.district_gimmicks_active:
        return {}
    markers = {}
    if world.gate is not None:
        markers["G"] = (world.gate_position, world.gate)
    if world.front_gate is not None:
        markers["F"] = (world.front_gate_position, world.front_gate)
    if world.shutter_position is not None and not world.shutter_closed:
        markers["S"] = (world.shutter_position, None)
    if world.bus_switch_position is not None and world.bus_broadcast_cooldown <= 0:
        markers["B"] = (world.bus_switch_position, None)
    bridge = world.bridge_puzzle
    if world.route_gimmicks_active and not bridge.bridge_down:
        if bridge.has_key:
            markers["C"] = (bridge.panel_position, None)
        else:
            markers["N"] = (bridge.note_position, None)
            markers["K"] = (bridge.key_position, None)
    return markers


class Renderer:
    def __init__(self):
        self.font = None
        self.play_hud = None
        self.player_visual = None
        self.combat_visual = None
        self.trash_can = None
        self.neighborhood_ground = None
        self.ground_file = None
        self.map_icons = None
        self.contract_previews = []
        self.truck_visual = None
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
        self._open_light_rows = {}
        self.glow_source = None
        self.nearby_light = None
        self.camera = (0.0, 0.0)
        self.choosing_delivery = False
        self.delivery_preview = 0
        self.map_open = False
        self.map_full_view = False
        self.abandon_confirmation = False
        self.bridge_note_open = False
        self.pause_page = None
        self.pause_index = 0
        self.audio_settings = AudioSettings()
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

    def load_neighborhood_ground(self):
        layout = self.delivery.contract.layout
        ground_file = layout.ground_file if layout is not None else "neighborhood/ground.png"
        if self.ground_file == ground_file:
            return
        world_w, world_h = self.delivery.world_size
        self.neighborhood_ground = load_atlas(BASE_DIR / "assets" / ground_file,
                                              [round(world_w / 2), round(world_h * GROUND_SCALE_Y / 2)])
        if p.SDL_SetTextureBlendMode(self.neighborhood_ground.texture, p.SDL_BLENDMODE_BLEND) != 0:
            raise RuntimeError(f"Ground blend mode failed: {p.SDL_GetError()!r}")
        self.ground_file = ground_file

    def load_neighborhood(self):
        self.combat_visual.load_zombie_appearances()
        self.load_neighborhood_ground()
        self.neighborhood_walls = {
            name: load_atlas(NEIGHBORHOOD_PATH / f"{name}.png", size)
            for name, size in WALL_TEXTURE_SIZES.items()
        }
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
        self.contract_previews = load_contract_previews(BASE_DIR / "assets/contract_previews",
                                                       tuple(PLAYABLE_CONTRACTS.values()))
        self.truck_visual = TruckVisual(BASE_DIR / "assets/vehicles")
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
        self.contract_previews.clear()
        self.truck_visual = None
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
        wall_geometry = tuple((id(wall), wall.x, wall.y, wall.width, wall.depth) for wall in walls)
        pose = (origin, angle, self.camera, self.shake_offset, self.ground_scale(), wall_geometry)
        if self.light is None or pose != self._light_pose:
            if self.delivery is not None and self._light_pose is not None and wall_geometry != self._light_pose[-1]:
                self.reset_streetlights()
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

    contract_card_at = staticmethod(contract_card_at)
    contract_dispatch_at = staticmethod(contract_dispatch_at)

    def draw_delivery_selection(self):
        display.clear()
        contracts = tuple(PLAYABLE_CONTRACTS.values())
        draw_contract_selection(self.play_hud, contracts, contracts,
                                self.delivery_preview, self.cursor, self.contract_previews, self.draw_contract_route,
                                self.draw_map_pin)

    def draw_contract_route(self, contract, viewport):
        x, top, width, height = viewport
        layout = contract.layout
        world_size = layout.world_size if layout is not None else TOWN_SIZE
        roads = layout.roads if layout is not None else TOWN_ROADS
        walls = layout.walls if layout is not None else TOWN_BASE_WALLS
        left, bottom, scale = self._map_layout(x, WINDOW_HEIGHT - top - height, width, height,
                                               world_bounds=(0, 0, *world_size))
        right, upper = left + world_size[0] * scale, bottom + world_size[1] * scale
        bounds = left, bottom, right, upper

        def map_point(x, y):
            return left + x * scale, bottom + y * scale

        draw_map_base(rectangle, p.draw_line, bounds, scale, world_size, roads, walls, draw_sprite=self._draw_map_sprite)
        self.draw_district_map_routes(contract, map_point)
        markers = [(map_point(*contract.pickup), "트럭" if contract.truck_position is not None else "수령지", MAP_PICKUP)]
        markers.extend((map_point(*stop.position), stop.name, MAP_DROPOFF) for stop in contract.stops)
        occupied = [(px - 9, py - 9, px + 9, py + 9) for (px, py), _, _ in markers]
        for (px, py), label, color in markers:
            self.draw_map_pin(px, py, color, pickup=color == MAP_PICKUP)
            _, label_width, _ = self.play_hud._label(label, HUD_SMALL, color)
            label_width += 10
            position = place_map_label((px, py), label_width, bounds, occupied, (-label_width - 12, -9), height=18)
            if position is not None:
                lx, ly = position
                p.draw_line(px, py, min(max(lx, px), lx + label_width), ly + 9, *color)
                rectangle(lx, ly, label_width, 18, MAP_LABEL)
                self.play_hud._text(label, round(lx) + 5, WINDOW_HEIGHT - 1 - round(ly + 9), HUD_SMALL, color)
        rectangle(left, bottom, right - left, upper - bottom, MAP_LABEL_EDGE, filled=False)

    @staticmethod
    def draw_map_heading(x, y, angle):
        p.draw_circle(x, y, MAP_PLAYER_RADIUS, *WHITE, filled=True)
        p.draw_circle(x, y, MAP_PLAYER_RADIUS - 2, *MAP_INK, filled=True)
        dx, dy = math.cos(angle), math.sin(angle)
        color = p.SDL_Color(*MAP_PLAYER, 255)
        points = ((10, 0), (-7, 7), (-4, 0), (-7, -7))
        vertices = (p.SDL_Vertex * len(points))(*(
            p.SDL_Vertex(p.SDL_FPoint(x + forward * dx - side * dy,
                                     WINDOW_HEIGHT - 1 - y - forward * dy - side * dx),
                         color, p.SDL_FPoint(0, 0))
            for forward, side in points
        ))
        indices = (ctypes.c_int * 6)(0, 1, 2, 0, 2, 3)
        if p.SDL_RenderGeometry(p.renderer, None, vertices, len(vertices), indices, len(indices)) != 0:
            raise RuntimeError(f"Map heading geometry failed: {p.SDL_GetError()!r}")

    @staticmethod
    def draw_map_truck(x, y, color):
        rectangle(x - 11, y - 8, 22, 16, MAP_LABEL)
        rectangle(x - 10, y - 7, 20, 14, color)
        rectangle(x - 7, y - 2, 8, 7, WHITE)
        rectangle(x + 1, y - 2, 5, 5, WHITE)
        rectangle(x - 6, y - 5, 3, 3, WHITE)
        rectangle(x + 3, y - 5, 3, 3, WHITE)

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
            if not (left <= x <= right and bottom <= y <= top):
                continue
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

    def _map_layout(self, x, y, viewport_width, viewport_height, *, world_bounds=None):
        west, south, east, north = world_bounds or (0, 0, *self.delivery.world_size)
        width, height = east - west, north - south
        scale = min(viewport_width / width, viewport_height / height)
        left = x + (viewport_width - width * scale) / 2 - west * scale
        bottom = y + (viewport_height - height * scale) / 2 - south * scale
        return left, bottom, scale

    def _map_detail_area(self):
        contract = self.delivery.contract
        return contract.layout.map_area if contract.layout is not None else (
            TRUCK_MAP_AREA if contract.truck_position is not None else None)

    def _map_detail_available(self):
        area = self._map_detail_area()
        if area is None:
            return False
        player = self.delivery.player
        west, south, east, north = area
        return west <= player.x <= east and south <= player.y <= north

    def _play_map_bounds(self):
        return self._map_detail_area() if self._map_detail_available() and not self.map_full_view else None

    @staticmethod
    def map_view_button_at(mouse_x, mouse_y):
        x, y, width, height = MAP_VIEW_BUTTON
        mouse_y = WINDOW_HEIGHT - 1 - mouse_y
        return x <= mouse_x < x + width and y <= mouse_y < y + height

    def toggle_map_view(self):
        if self._map_detail_available():
            self.map_full_view = not self.map_full_view

    def map_world_at(self, mouse_x, mouse_y):
        """Convert an SDL mouse position inside the live map to ground coordinates."""
        world_bounds = self._play_map_bounds()
        left, bottom, scale = self._map_layout(*PLAY_MAP_VIEWPORT, world_bounds=world_bounds)
        x = (mouse_x - left) / scale
        y = (WINDOW_HEIGHT - 1 - mouse_y - bottom) / scale
        west, south, east, north = world_bounds or (0, 0, *self.delivery.world_size)
        if west - 1e-9 <= x <= east + 1e-9 and south - 1e-9 <= y <= north + 1e-9:
            return min(east, max(west, x)), min(north, max(south, y))
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

    def map_walls_for(self, contract):
        world = self.delivery
        ignored = (world.truck_wall,)
        if contract is not world.contract:
            ignored += (*world.parking_walls, world.shutter_wall, world.gate, world.front_gate, *world.front_gate_fences)
            if world.bridge_puzzle is not None:
                ignored += world.bridge_puzzle.station_walls
        return [wall for wall in world.walls if wall not in ignored and getattr(wall, "texture", None) not in BRIDGE_TERRAIN]

    def draw_town_map(self, contract, x, y, viewport_width, viewport_height, player=None, *, world_bounds=None):
        world = self.delivery
        width, height = world.world_size
        origin_x, origin_y, scale = self._map_layout(x, y, viewport_width, viewport_height, world_bounds=world_bounds)

        def map_point(x, y):
            return origin_x + x * scale, origin_y + y * scale

        west, south, east, north = world_bounds or (0, 0, width, height)
        left, bottom = map_point(west, south)
        right, top = map_point(east, north)
        bounds = left, bottom, right, top
        active_contract = contract is world.contract
        puzzles = puzzle_markers(world) if active_contract and player is not None else {}
        shutter = world.shutter_wall if active_contract else None
        bridge = world.bridge_puzzle if active_contract else None
        show_east_detour = bridge is not None and player is not None and world.route_gimmicks_active
        map_walls = self.map_walls_for(contract)
        draw_map_base(rectangle, p.draw_line, bounds, scale, (width, height),
                      world.roads, map_walls, draw_sprite=self._draw_map_sprite, min_road_edge=1.5,
                      world_bounds=world_bounds)
        legend_right = left + (48 if world_bounds is not None else 151)
        occupied = [(left + 10, top - 60, legend_right, top - 5)]
        bus_road_y = 1702 if world_bounds is not None else 1720
        layout = contract.layout
        road_labels = (
            ((720, 80), "남쪽 큰길", MAP_ROAD_INK),
            ((3140, 958) if show_east_detour else (3110, 1007), "상점길", MAP_ALLEY_INK),
            ((2440, bus_road_y), "정류장길", MAP_ALLEY_INK),
        ) if layout is None else ()
        for point, label, color in road_labels:
            if not (west <= point[0] <= east and south <= point[1] <= north):
                continue
            px, py = map_point(*point)
            self.font.draw(px, py, label, color)
            occupied.append((px, py - 9, px + len(label) * 17, py + 9))

        route = []
        if player is not None:
            self.draw_district_map_routes(world.contract, map_point)
            route = [map_point(player.x, player.y), *(map_point(*point) for point in world.waypoints)]
            for start, end in zip(route, route[1:]):
                for dx, dy in ((-1, 0), (0, -1), (1, 0), (0, 1)):
                    p.draw_line(start[0] + dx, start[1] + dy, end[0] + dx, end[1] + dy, *MAP_LABEL)
            for start, end in zip(route, route[1:]):
                p.draw_line(*start, *end, *MAP_ROUTE_INK)

        captions = []

        def caption(position, label, ink=MAP_PAPER_INK, *, offset=(13, -11)):
            px, py = position
            if left <= px <= right and bottom <= py <= top:
                label_width = 17 * len(label) + 16
                captions.append((position, label, ink, label_width, offset))

        def mark_device(x, y, symbol, *, active=False, color=MAP_PICKUP):
            puzzle = symbol in puzzles
            px, py = x, y
            if puzzle:
                # Keep the blue player arrow readable when the player is beside a device.
                hx, hy = route[0]
                distance = math.hypot(x - hx, y - hy)
                clearance = MAP_PLAYER_RADIUS + 9
                if distance < clearance:
                    dx, dy = ((x - hx) / distance, (y - hy) / distance) if distance else (1, 0)
                    px, py = hx + dx * clearance, hy + dy * clearance
                    p.draw_line(x, y, px, py, *MAP_INK)
            self.draw_bridge_map_marker(px, py, symbol, active=active, active_color=color, puzzle=puzzle)
            occupied.append((px - 9, py - 10, px + 9, py + 10))
            return px, py

        if player is not None:
            hx, hy = route[0]
            radius = MAP_PLAYER_RADIUS
            occupied.append((hx - radius, hy - radius, hx + radius, hy + radius))
            caption(route[0], "내 위치", MAP_PLAYER_INK, offset=(radius + 6, -11))

        pickup_x, pickup_y = map_point(*contract.pickup)
        if contract.truck_position is not None:
            picking_up = player is None or world.parcel == "waiting"
            truck_color = MAP_PICKUP if picking_up else MAP_SAFE
            self.draw_map_truck(pickup_x, pickup_y, truck_color)
            occupied.append((pickup_x - 11, pickup_y - 8, pickup_x + 11, pickup_y + 8))
            caption((pickup_x, pickup_y), "수령 트럭" if picking_up else "복귀 트럭", truck_color,
                    offset=(16, -11))
        else:
            self.draw_map_pin(pickup_x, pickup_y, MAP_PICKUP, pickup=True)
            occupied.append((pickup_x - 7, pickup_y - 7, pickup_x + 7, pickup_y + 7))
        for stop in contract.stops:
            completed = player is not None and stop in world.completed_stops
            x, y = map_point(*stop.position)
            if completed:
                p.draw_circle(x, y, 5, *MAP_COMPLETED, filled=True)
                occupied.append((x - 5, y - 5, x + 5, y + 5))
                continue
            occupied.append((x - 9, y - 9, x + 9, y + 9))
            self.draw_map_pin(x, y, MAP_DROPOFF)
            caption((x, y), stop.name, MAP_DROPOFF, offset=(-17 * len(stop.name) - 28, -32))
        if contract.return_point is not None and contract.truck_position is None:
            safe_x, safe_y = map_point(*contract.return_point)
            occupied.append((safe_x - 8, safe_y - 8, safe_x + 8, safe_y + 8))
            self.draw_safe_map_marker(safe_x, safe_y, MAP_SAFE, backing=MAP_LABEL)
            caption((safe_x, safe_y), "안전지점", MAP_SAFE, offset=(-96, -11))
        district_gate = layout is not None and layout.gate is not None
        if active_contract and (REAR_HOME_STOP in contract.stops or district_gate):
            gate_x, gate_y = map_point(*world.gate_position)
            gate_closed = player is None or world.gate is not None
            marker = mark_device(gate_x, gate_y, "G", active=not gate_closed, color=MAP_OPEN_GATE)
            if district_gate:
                caption(marker, "정비창 철문", MAP_SAFE if not gate_closed else MAP_PAPER_INK)
        if active_contract and world.front_gate_position is not None:
            gate_x, gate_y = map_point(*world.front_gate_position)
            mark_device(gate_x, gate_y, "F", active=world.front_gate is None, color=MAP_OPEN_GATE)
        if active_contract and world.bus_switch_position is not None:
            switch_x, switch_y = map_point(*world.bus_switch_position)
            marker = mark_device(switch_x, switch_y, "B", active=world.bus_broadcast_cooldown > 0)
            if layout is not None and world.bus_speaker_position is not None:
                caption(marker, "방송 스위치", MAP_PAPER_INK)
                speaker_x, speaker_y = map_point(*world.bus_speaker_position)
                p.draw_circle(speaker_x, speaker_y, 6, *MAP_LABEL, filled=True)
                p.draw_circle(speaker_x, speaker_y, 4, *MAP_DETOUR, filled=True)
                occupied.append((speaker_x - 6, speaker_y - 6, speaker_x + 6, speaker_y + 6))
                caption((speaker_x, speaker_y), "스피커", MAP_DETOUR)
        if shutter is not None:
            sx, sy = map_point(shutter.x, shutter.y)
            marker_w, marker_h = max(4, shutter.width * scale), max(4, shutter.depth * scale)
            color = MAP_CLOSED_GATE if world.shutter_closed else MAP_OPEN_GATE
            rectangle(sx - 1, sy - 1, marker_w + 2, marker_h + 2, MAP_INK)
            rectangle(sx, sy, marker_w, marker_h, color)
            occupied.append((sx - 1, sy - 1, sx + marker_w + 1, sy + marker_h + 1))
            switch_x, switch_y = map_point(*world.shutter_position)
            mark_device(switch_x, switch_y, "S", active=world.shutter_closed)
            lot_x, lot_y = map_point(*world.shutter_lure)
            caption((lot_x, lot_y), "주차장", offset=(-32, 5))
        if bridge is not None:
            x, y, width, depth = bridge.channel_rect
            cx, cy = map_point(x, y)
            rectangle(cx, cy, width * scale, max(2, depth * scale), MAP_ROUTE_INK)
            next_stop = self.bridge_map_next_stop(world) if player is not None else None
            for position, symbol in ((bridge.key_position, "K"), (bridge.panel_position, "C")):
                px, py = map_point(*position)
                active = next_stop is not None and symbol == next_stop[0]
                marker = mark_device(px, py, symbol, active=active)
                if active:
                    caption(marker, next_stop[1], MAP_PICKUP, offset=(16, -11))
            if "N" in puzzles:
                marker = mark_device(*map_point(*puzzles["N"][0]), "N")
                caption(marker, "시설 쪽지", offset=(22, 10))
            bx, by = map_point(*bridge.bridge_position)
            if bridge.bridge_down:
                bridge_x, bridge_y, bridge_width, bridge_depth = bridge.bridge_rect
                deck_x, deck_y = map_point(bridge_x, bridge_y)
                deck_width, deck_depth = bridge_width * scale, bridge_depth * scale
                rectangle(deck_x, deck_y, deck_width, deck_depth, MAP_OPEN_GATE)
                rectangle(deck_x, deck_y, deck_width, deck_depth, MAP_SAFE, filled=False)
                p.draw_line(bx, deck_y - 4, bx, deck_y + deck_depth + 4, *MAP_SAFE)
                caption((bx, by), "다리 지름길", MAP_SAFE, offset=(cx + width * scale + 10 - bx, 6))
            else:
                rectangle(bx - 9, by - 4, 18, 8, MAP_INK)
                rectangle(bx - 7, by - 2, 14, 4, MAP_CLOSED_GATE)
            half_h = 9 if bridge.bridge_down else 4
            occupied.append((bx - 9, by - half_h, bx + 9, by + half_h))
            if show_east_detour:
                # Mark the same lane just north of the turn.
                entry_x, entry_y = map_point(2750, 1058)
                arrow_y = entry_y + 12
                p.draw_line(entry_x, entry_y - 6, entry_x, arrow_y, *MAP_DETOUR)
                for dx in (-4, 4):
                    p.draw_line(entry_x, arrow_y, entry_x + dx, arrow_y - 5, *MAP_DETOUR)
                offset = (24, 1) if world_bounds is not None else (74, 1)
                caption((entry_x, entry_y), "동쪽 우회", MAP_DETOUR, offset=offset)
                occupied.append((entry_x - 4, entry_y - 6, entry_x + 4, arrow_y))
        for wall in map_walls:
            if getattr(wall, "texture", None) == "shop" and SHOP_STOP not in contract.stops:
                caption(map_point(wall.x + wall.width / 2, wall.y + wall.depth), "상점")
            elif getattr(wall, "texture", None) == "bus-stop" and BUS_STOP not in contract.stops:
                caption(map_point(wall.x + wall.width / 2, wall.y + wall.depth), "정류장")
        if layout is not None:
            for x, y, name in layout.road_labels:
                if all(name != stop.name for stop in contract.stops):
                    caption(map_point(x, y), name, MAP_ALLEY_INK, offset=(-17 * len(name) - 28, -11))
        labels = []
        for anchor, label, ink, label_width, offset in captions:
            position = place_map_label(anchor, label_width, bounds, occupied, offset)
            if position is not None:
                label_x, label_y = position
                leader_x = min(max(anchor[0], label_x), label_x + label_width)
                p.draw_line(*anchor, leader_x, label_y + 11, *ink)
                labels.append((label_x, label_y, label_width, label, ink))
        if player is not None:
            self.draw_map_waypoints(bounds, route[1:], world.first_waypoint_number, occupied)
        for label in labels:
            self.draw_map_label(*label)

        compass_x, compass_y = left + 31, top - 39
        p.draw_circle(compass_x, compass_y, 17, *MAP_LABEL, filled=True)
        p.draw_circle(compass_x, compass_y, 17, *MAP_LABEL_EDGE)
        self.font.draw(compass_x - 5, compass_y + 24, "N", MAP_PAPER_INK)
        p.draw_line(compass_x, compass_y - 9, compass_x, compass_y + 9, *MAP_PAPER_INK)
        p.draw_line(compass_x - 5, compass_y + 2, compass_x, compass_y + 9, *MAP_PAPER_INK)
        p.draw_line(compass_x + 5, compass_y + 2, compass_x, compass_y + 9, *MAP_PAPER_INK)
        if world_bounds is None:
            scale_x, scale_y = left + 60, compass_y - 6
            half_scale = 200 * scale
            rectangle(scale_x, scale_y, half_scale, 4, MAP_PAPER_INK)
            rectangle(scale_x + half_scale, scale_y, half_scale, 4, MAP_LABEL)
            rectangle(scale_x, scale_y, 2 * half_scale, 4, MAP_PAPER_INK, filled=False)
            self.font.draw(scale_x, scale_y + 15, "400 px", MAP_PAPER_INK)
        rectangle(left, bottom, right - left, top - bottom, MAP_BORDER, filled=False)
        if player is not None:
            self.draw_map_heading(*route[0], player.aim_angle)

    @staticmethod
    def draw_district_map_routes(contract, map_point):
        routes = []
        if SHOP_STOP in contract.stops:
            routes.append(((2110, 1012), (2110, 1235), (2095, 1435), (2095, 1655), (2170, 1740)))
        if BUS_STOP in contract.stops:
            routes.extend((((2170, 1740), (2170, 1860), BUS_STOP.position),
                           ((2394, 1740), (2394, 1860), BUS_STOP.position)))
        if MANAGEMENT_STOP in contract.stops:
            routes.append(((2750, 987), (2750, 1400), (2960, 1400), (2960, 1740), (2435, 1740)))
        if FRONT_HOME_STOP in contract.stops:
            routes.append(((3180, 1880), (3180, 1969), FRONT_HOME_STOP.position))
        if REAR_HOME_STOP in contract.stops:
            routes.extend((((3230, 2080), (3230, 2233), (3180, 2233)),
                           ((3380, 2240), (3380, 2358), (2820, 2358), (2820, 2256),
                            (3080, 2256), (3115, 2227))))
        if contract.layout is not None:
            routes.extend(contract.layout.detour_routes)
        for route in routes:
            points = [map_point(*point) for point in route]
            for start, end in zip(points, points[1:]):
                length = math.dist(start, end)
                if not length:
                    continue
                dx, dy = end[0] - start[0], end[1] - start[1]
                edge_x, edge_y = (0, 1) if abs(dx) >= abs(dy) else (1, 0)
                for offset in range(0, math.ceil(length), 10):
                    a, b = offset / length, min(length, offset + 5) / length
                    ax, ay = start[0] + dx * a, start[1] + dy * a
                    bx, by = start[0] + dx * b, start[1] + dy * b
                    p.draw_line(ax, ay, bx, by, *MAP_DETOUR)
                    p.draw_line(ax + edge_x, ay + edge_y, bx + edge_x, by + edge_y, *MAP_DETOUR)

    @staticmethod
    def bridge_map_next_stop(world):
        bridge = world.bridge_puzzle
        if bridge is None or not world.route_gimmicks_active or bridge.bridge_down:
            return None
        if bridge.has_key:
            return "C", "관리실", "회로 연결"
        return "K", "경비초소", "열쇠 찾기"

    @staticmethod
    def draw_puzzle_dot(x, y):
        p.draw_circle(x, y, 7, *MAP_INK, filled=True)
        p.draw_circle(x, y, 4, *PUZZLE_DOT, filled=True)

    def draw_bridge_map_marker(self, x, y, symbol, *, active=False, active_color=MAP_PICKUP, puzzle=False):
        if puzzle:
            self.draw_puzzle_dot(x, y)
            return
        if active:
            rectangle(x - 9, y - 10, 18, 20, active_color)
        rectangle(x - 7, y - 8, 14, 16, MAP_LABEL)
        if not active:
            rectangle(x - 7, y - 8, 14, 16, MAP_PAPER_INK, filled=False)
        self.font.draw(x - 5, y, symbol, MAP_PAPER_INK)

    def draw_map(self, player):
        world = self.delivery
        display.clear(MAP_VIEW_BG)
        world_bounds = self._play_map_bounds()
        if world_bounds is None:
            self.draw_town_map(world.contract, *PLAY_MAP_VIEWPORT, player)
        else:
            west, south, east, north = world_bounds
            left, bottom, scale = self._map_layout(*PLAY_MAP_VIEWPORT, world_bounds=world_bounds)
            x, right = round(left + west * scale), round(left + east * scale)
            y = WINDOW_HEIGHT - 1 - round(bottom + north * scale)
            end = WINDOW_HEIGHT - 1 - round(bottom + south * scale)
            clip = p.SDL_Rect(x, y, right - x + 1, end - y + 1)
            p.SDL_RenderSetClipRect(p.renderer, ctypes.byref(clip))
            try:
                self.draw_town_map(world.contract, *PLAY_MAP_VIEWPORT, player, world_bounds=world_bounds)
            finally:
                p.SDL_RenderSetClipRect(p.renderer, None)
        rectangle(64, 650, 1152, 48, MAP_VIEW_PAPER)
        rectangle(64, 650, 1152, 48, MAP_VIEW_EDGE, filled=False)
        if self._map_detail_available():
            self.font.draw(82, 674, "배달 구역 지도" if world_bounds else "마을 전체 지도", MAP_PAPER_INK)
            x, y, width, height = MAP_VIEW_BUTTON
            rectangle(x, y, width, height, MAP_LABEL)
            rectangle(x, y, width, height, MAP_LABEL_EDGE, filled=False)
            button = "Tab  마을 전체" if world_bounds else "Tab  배달 구역"
            self.font.draw(x + 14, y + height / 2, button, MAP_PAPER_INK)
        else:
            layout = world.contract.layout
            title = "마을 전체 지도" if layout is None else f"{world.contract.name.removesuffix(' 왕복')} 지도"
            self.font.draw(82, 674, title, MAP_PAPER_INK)
            if self._map_detail_area() is not None:
                self.font.draw(700, 674, "현재 위치가 배달 구역 밖", MAP_PAPER_INK)
        self.font.draw(1012, 674, "지도 확인 중 일시정지", MAP_PAPER_INK)

        side = 880
        rectangle(side, 104, 336, 528, MAP_VIEW_PANEL)
        rectangle(side, 104, 336, 528, MAP_VIEW_EDGE, filled=False)
        self.font.draw(side + 24, 602, "다음 목표", MAP_VIEW_TEXT)
        self.font.draw(side + 238, 602, f"{len(world.completed_stops)} / {len(world.contract.stops)}", MAP_VIEW_TEXT)
        truck_route = world.contract.truck_position is not None
        if world.returning:
            objective = "출발 트럭으로 복귀"
            accent = SAFE_GREEN
            target = "추격을 끊고 복귀" if world.return_blocked else "트럭 문 앞에서 E 길게"
        elif world.parcel == "waiting":
            objective = "트럭에서 수령" if truck_route else "택배 수령"
            target, accent = "주황색 수령지에서 E 길게", ORANGE
        else:
            remaining = world.remaining_stops
            objective = f"남은 배송지 {len(remaining)}곳" if len(remaining) > 1 else remaining[0].name
            target, accent = "배송함에서 E 길게", MAP_VIEW_TEXT
        self.font.draw(side + 24, 566, objective, accent)
        self.font.draw(side + 24, 532, target, MAP_VIEW_TEXT)
        p.draw_line(side + 24, 504, side + 312, 504, *MAP_VIEW_EDGE)
        self.draw_map_checklist(world, side)
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

    def draw_map_checklist(self, world, side):
        left, right = side + 24, side + 312
        puzzles = puzzle_markers(world)
        self.font.draw(left, 478, "배송 목록", MAP_VIEW_TEXT)
        for row, stop in enumerate(world.contract.stops):
            y = 449 - row * 28
            completed = stop in world.completed_stops
            self.draw_map_pin(left + 8, y, MAP_COMPLETED if completed else MAP_DROPOFF)
            self.font.draw(left + 24, y, stop.name, MAP_VIEW_MUTED if completed else MAP_VIEW_TEXT)
            self.font.draw(right - 62, y, "완료" if completed else "남음", MAP_VIEW_MUTED if completed else MAP_VIEW_TEXT)
        p.draw_line(left, 370, right, 370, *MAP_VIEW_EDGE)
        self.font.draw(left, 348, "장치와 우회로", MAP_VIEW_TEXT)

        features = []
        if world.shutter_wall is not None:
            state = "닫힘" if world.shutter_closed else "열림"
            features.append(("S", f"주차장 셔터 · {state}", world.shutter_closed, MAP_PICKUP))
        if world.bus_switch_position is not None:
            cooldown = world.bus_broadcast_cooldown
            district = world.contract.layout is not None
            title = "스피커 유도" if district else "정류장 안내방송"
            detour = "서쪽 우회" if district else "동·서 골목"
            status = f"대기 {math.ceil(cooldown)}초" if cooldown > 0 else detour
            features.append(("B", f"{title} · {status}", cooldown > 0, MAP_PICKUP))
        if world.front_gate_position is not None:
            opened = world.front_gate is None
            label = "앞문 철문 · 열림" if opened else "앞문 철문 · 동쪽 골목"
            features.append(("F", label, opened, MAP_OPEN_GATE))
        if REAR_HOME_STOP in world.contract.stops:
            opened = world.gate is None
            label = "뒷문 철문 · 열림" if opened else "뒷문 철문 · 창고 옆길"
            features.append(("G", label, opened, MAP_OPEN_GATE))
        if world.contract.layout is not None and world.contract.layout.gate is not None:
            opened = world.gate is None
            label = "정비창 철문 · 열림" if opened else "정비창 철문 · 서쪽 우회"
            features.append(("G", label, opened, MAP_OPEN_GATE))
        bridge = world.bridge_puzzle
        if bridge is not None:
            next_stop = self.bridge_map_next_stop(world)
            active = next_stop[0] if next_stop is not None else None
            features.extend((("K", "경비초소 · 열쇠 수령" if bridge.has_key else "경비초소 · 열쇠 찾기",
                              active == "K", MAP_PICKUP),
                             ("C", "관리실 · 회로 연결", active == "C", MAP_PICKUP),
                             (None, "다리 지름길 · 개방" if bridge.bridge_down else "다리 · 동쪽 우회",
                              bridge.bridge_down, MAP_OPEN_GATE)))
        for row, (symbol, label, active, color) in enumerate(features):
            y = 320 - row * 27
            if symbol is None:
                rectangle(left, y - 2, 17, 4, MAP_OPEN_GATE if active else MAP_CLOSED_GATE)
            else:
                self.draw_bridge_map_marker(left + 8, y, symbol, active=active, active_color=color,
                                            puzzle=symbol in puzzles)
            self.font.draw(left + 25, y, label, MAP_VIEW_TEXT)

        p.draw_line(left, 186, right, 186, *MAP_VIEW_EDGE)
        for dx in (0, 8, 16):
            rectangle(left + dx, 166, 5, 2, SAFE_GREEN)
        self.font.draw(left + 25, 167, "우회 골목", MAP_VIEW_TEXT)
        if world.contract.truck_position is not None:
            picking_up = world.parcel == "waiting"
            self.draw_map_truck(left + 164, 167, MAP_PICKUP if picking_up else MAP_SAFE)
            pickup_label = "수령 트럭" if picking_up else "복귀 트럭"
        else:
            self.draw_map_pin(left + 164, 167, MAP_PICKUP, pickup=True)
            pickup_label = "수령지"
        self.font.draw(left + 180, 167, pickup_label, MAP_VIEW_TEXT)
        self.draw_map_heading(left + 7, 141, 0)
        self.font.draw(left + 25, 141, "현재 위치", MAP_VIEW_TEXT)
        self.draw_map_waypoint(left + 164, 141, 1)
        self.font.draw(left + 180, 141, "경유지", MAP_VIEW_TEXT)
        self.draw_puzzle_dot(left + 7, 117)
        self.font.draw(left + 25, 117, "사용 가능 퍼즐", MAP_VIEW_TEXT)

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
        building = texture in BUILDING_TEXTURES
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

        roof_mask = [(px, py + height) for px, py in beam_mask] if beam_mask else None
        front_width = front[1][0] - front[0][0]
        side_band = min(1, ROOF_LIGHT_BAND / front_width)
        edges = (
            (1, wall.y, wall.x, wall.width, "front"),
            (1, wall.y + wall.depth, wall.x, wall.width, "back"),
            (0, wall.x, wall.y, wall.depth, "left"),
            (0, wall.x + wall.width, wall.y, wall.depth, "right"),
        )
        if building and image is not None:
            strong_shades = ((187, 154, 110), (130, 128, 118), (123, 115, 106))
        elif image is not None:
            strong_shades = ((178, 147, 105), (140, 123, 102), (155, 131, 103))
        else:
            strong_shades = ((53, 47, 40), (45, 41, 38), (155, 131, 103))
        passes = []
        if glow_outline:
            dim_shades = tuple(map(dim_color, strong_shades))
            passes.extend((edge, glow_outline, None, dim_shades) for edge in edges)
        passes.extend((edge, outline, roof_mask if index == 0 else None, strong_shades)
                      for edge in edges for index, outline in enumerate(outlines))
        for (axis, boundary, offset, length, edge), outline, mask, shades in passes:
            facade_shade, roof_shade, side_shade = shades
            # The roof of a low obstacle fits in the beam instead of the
            # narrow rim used to suggest the height of a building.
            low_roof = low_obstacle and mask is not None
            band_width = BUILDING_ROOF_LIGHT_BAND if building and mask is not None else ROOF_LIGHT_BAND
            roof_depth = 1 if low_roof else min(1, band_width / depth)
            roof_width = 1 if low_roof else min(1, band_width / front_width)
            falloff = 80 if low_roof else 0
            for low, high in wall_edge_spans(wall, outline, axis, boundary):
                start = max(0, (low - offset) / length)
                end = min(1, (high - offset) / length)
                if start >= end:
                    continue
                if edge == "front":
                    self.draw_wall_plane(image, front, seam, 1, facade_shade, (start, 0, end, 1), opacity=opacity)
                    roof_bounds = (start, 0, end, roof_depth)
                    roof_alpha = (255, 255, falloff, falloff)
                elif edge == "back":
                    roof_bounds = (start, 1 - roof_depth, end, 1)
                    roof_alpha = (falloff, falloff, 255, 255)
                elif edge == "left":
                    roof_bounds = (0, start, roof_width, end)
                    roof_alpha = (255, falloff, falloff, 255)
                else:
                    roof_bounds = (1 - roof_width, start, 1, end)
                    roof_alpha = (falloff, 255, 255, falloff)
                    if oblique:
                        self.draw_wall_plane(side_image, side, 0, 1, side_shade, (start, 0, end, 1), opacity=opacity)
                if low_obstacle and edge in ("left", "right"):
                    # Show the end of a low obstacle when approached along the lane.
                    band = side_band * min(1, (end - start) * 2)
                    bounds = (0, 0, band, 1) if edge == "left" else (1 - band, 0, 1, 1)
                    self.draw_wall_plane(image, front, seam, 1, facade_shade, bounds, opacity=opacity)
                if long_shutter and edge in ("left", "right"):
                    # The shutter opening follows the alley depth in the current projection.
                    face = quad(x, y, wall.width, height + depth)
                    self.draw_wall_plane(image, face, 0, 1, facade_shade, (0, start, 1, end), opacity=opacity)
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

    def actor_light_spans(self, position, screen_x, foot_y, *, standing=True, light_sources=None,
                         wall_shadow_at_feet=False):
        if light_sources is None:
            light_sources = self.light_sources
        sources = []
        for light, rows in light_sources:
            columns = light_depth_columns(light, position[1], screen_x - position[0])
            if not columns:
                continue
            if wall_shadow_at_feet and light.walls:
                # Height samples keep the beam's shape. Only the feet determine wall shadow depth.
                if light not in self._open_light_rows:
                    self._open_light_rows[light] = light_source_rows(light.open_light, self.project)
                rows = self._open_light_rows[light]
            sources.append((rows, columns))
        if not sources:
            return None
        ground_scale = self.ground_scale()

        def spans(row):
            sample = zombie_light_row(row, foot_y, ground_scale) if standing else row
            return merge_light_spans(span for rows, columns in sources
                                     for span in clip_light_columns(rows.get(sample, ()), columns))

        return spans

    def draw_lit_prop(self, position, image, *, lift=0):
        x, foot_y = self.project(*position)
        y = foot_y + lift
        width, height = image.w * 2, image.h * 2
        bounds = (x - image.w, y, width, height)

        def draw():
            image.draw(x, y + image.h, width, height)

        glow_spans = self.glow_at_ground_depth(position, x)
        if glow_spans is not None:
            ground_scale = self.ground_scale()
            self.draw_lit_region(bounds, lambda: draw_dimmed_texture(image.texture, draw),
                                 row_spans=lambda row: glow_spans(zombie_light_row(row, foot_y, ground_scale)))
        spans = self.actor_light_spans(position, x, foot_y)
        if spans is not None:
            self.draw_lit_region(bounds, draw, row_spans=spans)

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

    def draw_world_puzzle_marker(self, position, origin, walls, gate):
        if math.dist(position, origin) > PUZZLE_MARKER_DISTANCE:
            return
        if any(wall is not gate and getattr(wall, "texture", None) != "bridge-channel"
               and wall_blocks(origin, position, wall) for wall in walls):
            return
        x, y = self.project(*position)
        if gate is not None:
            y += wall_height(gate) + gate.depth * self.ground_scale() / 2 + 9
        else:
            y += 42
        player_x, player_y = self.project(*origin)
        head_y = player_y + self.player_visual.metadata["display_height"] * self.player_visual.display_scale
        if abs(x - player_x) < 19 and player_y <= y <= head_y + 7:
            x = player_x + (23 if x >= player_x else -23)
        if not (7 <= x < WINDOW_WIDTH - 7 and 7 <= y < WINDOW_HEIGHT - 7):
            return
        ground_scale = self.ground_scale()
        for wall in walls:
            texture = getattr(wall, "texture", None)
            if wall is gate or wall.y >= position[1] or texture == "bridge-channel" or self.building_opacity(wall) == 0:
                continue
            left, bottom = self.project(wall.x, wall.y)
            if wall_covers(wall, left, bottom, x, y, self.wall_alpha.get(texture), ground_scale=ground_scale):
                return
        self.draw_puzzle_dot(x, y)

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
        if self.glow_source is not None:
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
        if self.glow_source is not None:
            glow_columns = outline_columns(self.glow_source[0])
            self.draw_lit_region(bounds, lambda: draw(dimmed=True), row_spans=lambda _: glow_columns)
        columns = merge_light_spans(span for light, _ in self.light_sources for span in outline_columns(light))
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
        bounds = self.combat_visual.zombie_rect(zombie, x, y)
        left, _, width, _ = bounds
        if left + width <= 0 or left >= WINDOW_WIDTH:
            return

        def draw():
            self.combat_visual.draw_zombie(zombie, x, y)

        position = zombie.x, zombie.y
        if self.glow_source is not None and (opacity := zombie_glow_opacity(self.glow_source[0], position)):
            glow_spans = self.actor_light_spans(position, x, y, standing=zombie.alive,
                                                 light_sources=(self.glow_source,), wall_shadow_at_feet=zombie.alive)
            if glow_spans is not None:
                texture = self.combat_visual.zombie_texture(zombie)
                if p.SDL_SetTextureAlphaMod(texture, opacity) != 0:
                    raise RuntimeError(f"Nearby zombie opacity failed: {p.SDL_GetError()!r}")
                try:
                    self.draw_lit_region(bounds, draw, row_spans=glow_spans)
                finally:
                    p.SDL_SetTextureAlphaMod(texture, 255)

        spans = self.actor_light_spans(position, x, y, standing=zombie.alive, wall_shadow_at_feet=zombie.alive)
        if spans is None:
            return
        self.draw_lit_region(bounds, draw, row_spans=spans)
        self.draw_zombie_markers(zombie, combat, attack, x, y, row_spans=spans)

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
        elif self.pause_page is not None:
            volumes = tuple(getattr(self.audio_settings, field) for field in PAUSE_VOLUME_FIELDS)
            self.play_hud.draw_pause(self.pause_page, self.pause_index, volumes,
                                     integer_scale=display.integer_scale_enabled())

    def handle_pause_key(self, key):
        if key == p.SDLK_ESCAPE:
            if self.pause_page == "main":
                self.pause_page = None
            else:
                self.pause_index = 1 if self.pause_page == "controls" else 2
                self.pause_page = "main"
            return None
        if self.pause_page == "controls":
            return None
        if key in (p.SDLK_UP, p.SDLK_DOWN):
            options = len(PAUSE_MENU) if self.pause_page == "main" else len(PAUSE_VOLUME_FIELDS)
            step = 1 if key == p.SDLK_DOWN else -1
            self.pause_index = (self.pause_index + step) % options
        elif self.pause_page == "audio" and key in (p.SDLK_LEFT, p.SDLK_RIGHT):
            field = PAUSE_VOLUME_FIELDS[self.pause_index]
            step = PAUSE_VOLUME_STEP if key == p.SDLK_RIGHT else -PAUSE_VOLUME_STEP
            setattr(self.audio_settings, field, max(0, min(100, getattr(self.audio_settings, field) + step)))
        elif self.pause_page == "main" and key in (p.SDLK_RETURN, p.SDLK_KP_ENTER):
            if self.pause_index == 0:
                self.pause_page = None
            elif self.pause_index == 1:
                self.pause_page = "controls"
            elif self.pause_index == 2:
                self.pause_page = "audio"
                self.pause_index = 0
            elif self.pause_index == len(PAUSE_MENU) - 1:
                return "scale"
            else:
                return "abandon" if self.pause_index == 3 else "quit"
        return None

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
        display.clear()
        delivery = self.delivery
        phase = delivery.mission_phase if delivery is not None else None
        truck = delivery.truck_footprint if delivery is not None else None
        truck_step = courier_step(delivery) if truck is not None else None
        courier_in_truck = (delivery is not None and delivery.contract.truck_position is not None
                            and phase in ("arriving", "parking", "departing", "finished"))
        action_pickup = (truck is not None and phase == "unloading" and delivery.interaction_action == "pickup")
        pickup_index = pickup_frame(delivery.interaction_progress) if action_pickup else None
        origin = (player.x, player.y)
        world_size = self.combat.world_size if self.combat is not None else (WORLD_WIDTH, WORLD_HEIGHT)
        beam, *lamps = self.prepare_light(player, walls, aim).lights
        street_lamps = tuple(lamps)
        truck_lights_only = truck is not None and delivery.route_sequence_active
        if truck_lights_only:
            x, y, _, depth = truck
            lamps.append(Flashlight((x - 2, y + depth * .45), math.pi, self.light_walls(walls), world_size,
                                    radius=175.0, half_angle=.34))
        glow = None if courier_in_truck else self.nearby_light
        if truck_step is not None:
            glow = (nearby_glow(truck_step.position, self.light_walls(walls), world_size)
                    if truck_step.opacity > 0 else None)
        glow_outline = glow.outline() if glow is not None else ()
        glow_walls = {id(wall) for wall in glow.walls} if glow is not None else set()
        # Station labels and status marks remain reserved for strong lighting.
        self.glow_source = (glow, light_source_rows(glow, self.project)) if glow is not None else None
        light_sources = lamps if truck_lights_only or courier_in_truck else (beam, *lamps)
        self._open_light_rows.clear()
        self.light_sources = tuple((source, light_source_rows(source, self.project)) for source in light_sources)
        self.light_rows = combined_light_rows([rows for _, rows in self.light_sources])
        beam_outline = () if truck_lights_only or courier_in_truck else beam.outline()
        # Wall hits select the facade spans. The roof uses the open beam projected at roof height.
        open_beam = beam.open_light
        beam_mask = []
        for point in (origin, *(point for point, _ in open_beam.outline())):
            x, y = self.project(*point)
            beam_mask.append((x, y + 1))
        lamp_outlines = tuple(lamp.outline() for lamp in lamps)
        if glow is not None:
            glow_color = (NEARBY_GLOW_COLOR if truck_step is None else
                          tuple(round(value * truck_step.opacity) for value in NEARBY_GLOW_COLOR))
            self.draw_ground_light(glow, glow_outline, glow_color, (0, 0, 0), feathered=True)
        if not truck_lights_only and not courier_in_truck:
            self.draw_ground_light(beam, beam_outline, BEAM_GROUND_EDGE, BEAM_GROUND_FALLOFF, feathered=True)
        self.draw_streetlight_pools(lamps, lamp_outlines)
        bridge = delivery.bridge_puzzle if delivery is not None else None
        defeated = delivery is not None and delivery.result == "defeated"
        if bridge is not None:
            self.draw_bridge_terrain(bridge)
        outlines = (beam_outline, *lamp_outlines)
        self.draw_noise_pulse(self.sprint_pulse, self.sprint_pulse_remaining, TEAL)
        self.draw_noise_pulse(self.bottle_pulse, self.bottle_pulse_remaining, ORANGE)
        self.draw_noise_pulse(self.vehicle_alarm, self.vehicle_alarm_remaining, ORANGE,
                              duration=VEHICLE_ALARM_DURATION)
        foot = self.project(*(origin if truck_step is None else truck_step.position))
        pickup_pose = None
        if pickup_index is not None:
            scale = self.player_visual.metadata["display_height"] / 64 * self.player_visual.display_scale
            pickup_pose = (foot, pickup_facing(origin, delivery.contract.truck_door_position), pickup_index, scale)
        combat = getattr(self, "combat", None)
        attack = combat.attack if combat is not None else None
        courier_style = {"empty_handed": delivery.parcel != "carrying"} if delivery is not None else {}
        bottles = []
        stations = ()
        truck_reveal = 0.0
        if delivery is not None:
            if truck is not None:
                door = delivery.contract.truck_door_position
                if delivery.route_sequence_active:
                    truck_reveal = 1.0
                elif self.nearby_light.contains(door):
                    truck_reveal = min(1.0, max(0.0, (self.nearby_light.radius - math.dist(origin, door)) / 40))
            if delivery.parcel == "waiting":
                stations = (delivery.pickup,) if truck is None else ()
            else:
                stations = tuple(stop.position for stop in delivery.remaining_stops)
            if delivery.returning:
                self.draw_safe_zone(delivery.contract.return_point, origin, walls, blocked=delivery.return_blocked)
            if delivery.district_gimmicks_active:
                if delivery.shutter_position is not None:
                    stations = (*stations, delivery.shutter_position)
                    if not delivery.shutter_closed:
                        self.draw_shutter_entrance(delivery.shutter_wall)
                if delivery.bus_switch_position is not None:
                    stations = (*stations, delivery.bus_switch_position, delivery.bus_speaker_position)
            if delivery.route_gimmicks_active or (bridge is not None and defeated and delivery.parcel == "delivered"):
                stations = (*stations, bridge.key_position, bridge.panel_position)
                if delivery.route_gimmicks_active:
                    stations = (*stations, bridge.note_position)
            bottles.extend((x, y, 0) for x, y in delivery.bottle_pickups)
            flight = delivery.bottle_flight
            if flight is not None:
                progress = flight.progress
                x, y = (start + (end - start) * progress for start, end in zip(flight.origin, flight.destination))
                lift = (1 - progress) * (18 + 88 * progress)
                bottles.append((x, y, lift))
        courier_depth = player if truck_step is None else replace(player, x=truck_step.position[0], y=truck_step.position[1])
        for kind, actor in sorted_drawables(courier_depth, walls, zombies=combat.zombies if combat else (),
                                            prop=TRASH_CAN_POSITION if delivery is None else None,
                                            stations=stations,
                                            lamps=(lamp.origin for lamp in street_lamps),
                                            street_props=delivery.props if delivery is not None else (),
                                            bottles=bottles, truck=truck):
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
                elif actor == delivery.bus_switch_position:
                    cooling = delivery.bus_broadcast_cooldown > 0
                    self.draw_control_box(actor, "방송 대기" if cooling else "안내방송", ORANGE if cooling else TEAL,
                                          label_width=96)
                elif actor == delivery.bus_speaker_position:
                    self.draw_control_box(actor, "스피커", ORANGE if delivery.bus_broadcast_cooldown > 0 else TEAL)
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
            elif kind == "truck":
                door = "closed"
                if phase == "unloading":
                    door = "cargo_empty" if pickup_index is not None and pickup_index >= 2 else "cargo"
                elif truck_step is not None:
                    door = "cab"
                bounds = truck_bounds(self.project, actor)
                if delivery.route_sequence_active:
                    self.truck_visual.draw(bounds, door)
                else:
                    if truck_reveal > 0:
                        draw_dimmed_texture(self.truck_visual.image.texture, lambda: self.truck_visual.draw(bounds, door))
                    self.draw_lit_region(bounds, lambda: self.truck_visual.draw(bounds, door))
                if pickup_pose is not None:
                    # The courier leans over the hatch while the body of the truck covers their legs.
                    self.truck_visual.draw_pickup(*pickup_pose, upper_body=True)
            elif kind == "wall":
                texture = getattr(actor, "texture", None)
                if texture == "delivery-truck":
                    continue
                if texture in BRIDGE_TERRAIN:
                    if texture == "bridge-raised":
                        self.draw_raised_bridge(actor)
                    continue
                opacity = self.building_opacity(actor)
                if (truck_reveal > 0 and texture in BUILDING_TEXTURES
                        and actor.y + actor.depth <= truck[1]
                        and actor.x < truck[0] + truck[2] and actor.x + actor.width > truck[0]
                        and self.project(actor.x, actor.y + actor.depth)[1] + wall_height(actor)
                        > self.project(truck[0], truck[1])[1]):
                    opacity = min(opacity, 1 - truck_reveal)
                if opacity > 0.0:
                    self.wall(actor, outlines, beam_mask, glow_outline=glow_outline if id(actor) in glow_walls else (),
                              opacity=opacity)
            elif kind == "zombie":
                if defeat_attacker is not None and actor is defeat_attacker[0]:
                    actor = defeat_attacker[1]
                self.draw_lit_zombie(actor, combat, attack)
            else:
                if courier_in_truck:
                    continue
                if truck_step is not None:
                    self.player_visual.draw(*foot, empty_handed=True, pose=(truck_step.facing, truck_step.frame),
                                            opacity=truck_step.opacity)
                    continue
                if pickup_pose is not None:
                    self.truck_visual.draw_pickup(*pickup_pose)
                elif defeated:
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
        if delivery is not None:
            for position, gate in puzzle_markers(delivery).values():
                self.draw_world_puzzle_marker(position, origin, walls, gate)

    def draw_nearby_action(self, foot_x, foot_y):
        world = self.delivery
        key = "E"
        progress = None
        if (action := world.interaction_action) is not None:
            _, label, _ = INTERACTION_LABELS[action]
            progress = world.interaction_progress
        elif (action := world.interaction_candidate) is not None:
            label, _, _ = INTERACTION_LABELS[action]
        elif world.can_read_bridge_note():
            label = "쪽지 읽기"
        elif world.nearby_bottle is not None:
            key, label = "F", "빈 병 줍기"
        else:
            return
        head_y = foot_y + self.player_visual.metadata["display_height"] * self.player_visual.display_scale
        self.play_hud.draw_action_prompt(foot_x, head_y, key, label, progress=progress)

    def _draw_overlay(self, player, target, aim, focused, defeat_elapsed):
        delivery = self.delivery
        if delivery is not None and delivery.route_sequence_active:
            self.play_hud.draw(delivery, self.light, aim, focused=focused, alarm=False)
            return
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
                waypoint_direction = None
                if delivery.waypoints:
                    waypoint_x, waypoint_y = self.project(*delivery.waypoints[0])
                    waypoint_direction = (waypoint_x - foot[0], foot[1] - waypoint_y)
                self.play_hud.draw(delivery, self.light, aim, focused=focused,
                                   alarm=self.vehicle_alarm_remaining > 0,
                                   waypoint_direction=waypoint_direction)
                bridge = delivery.bridge_puzzle
                if (focused and self.pause_page is None and not self.bridge_note_open
                        and not self.abandon_confirmation and (bridge is None or not bridge.panel_open)):
                    self.draw_nearby_action(*foot)
            else:
                self.draw_delivery_result()
            return

        self.font.draw(24, 683, "Dead Route  |  전투 검수", WHITE)
        self.font.draw(24, 651, "WASD 이동 · Shift 달리기 · Ctrl 잠행 · 마우스 조준 · 좌클릭 공격 · R 재시작 · Esc 종료", WHITE)
        if combat is not None:
            self.font.draw(24, 620, f"HP {combat.player_health_percent}% · 좀비 {combat.zombie.health_percent}%", WHITE)
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
    width, height = ctypes.c_int(), ctypes.c_int()
    if p.SDL_GetRendererOutputSize(p.renderer, ctypes.byref(width), ctypes.byref(height)) != 0:
        raise RuntimeError(f"SDL capture size query failed: {p.SDL_GetError()!r}")
    surface = p.SDL_CreateRGBSurfaceWithFormat(
        0, width.value, height.value, 32, p.SDL_PIXELFORMAT_ARGB8888)
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
        if (event.type == p.SDL_WINDOWEVENT
                and event.window.event in (p.SDL_WINDOWEVENT_SIZE_CHANGED, p.SDL_WINDOWEVENT_DISPLAY_CHANGED)
                and display.integer_scale_enabled() and display.set_integer_scale(True)):
            # Queued pointer events may have been filtered with the old viewport.
            p.SDL_FlushEvent(p.SDL_MOUSEMOTION)
            p.SDL_FlushEvent(p.SDL_MOUSEBUTTONDOWN)
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
        with display.frame():
            opening.draw(elapsed, renderer.font, renderer.player_visual, renderer.combat_visual.metadata["zombie"], art)
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
            with display.frame():
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
    finally:
        audio.stop()


def run(smoke_test=False, *, show_opening=False, practice=False, windowed=False, integer_scale=False):
    renderer = None
    music = None
    zombie_audio = None
    cutscene_art = None
    delivery_run = not (smoke_test or practice)
    delivery_audio = DeliveryAudioState() if delivery_run else None
    try:
        p.SDL_SetHint(p.SDL_HINT_WINDOWS_DPI_AWARENESS, b"permonitorv2")
        p.open_canvas(WINDOW_WIDTH, WINDOW_HEIGHT, sync=True)
        if not p.renderer:
            p.renderer = p.SDL_CreateRenderer(p.window, -1, p.SDL_RENDERER_SOFTWARE)
        if not p.renderer:
            raise RuntimeError(f"SDL renderer initialization failed: {p.SDL_GetError()!r}")
        p.hide_lattice()
        p.SDL_SetWindowTitle(p.window, b"Dead Route" if delivery_run else b"Dead Route - R2-ZA")
        display.configure(fullscreen=not (windowed or smoke_test), integer_scale=integer_scale)
        p.SDL_SetRenderDrawBlendMode(p.renderer, p.SDL_BLENDMODE_BLEND)
        renderer = Renderer()
        if delivery_run:
            cutscene_art = opening.CutsceneArt(BASE_DIR / "assets/cutscenes")
        if not smoke_test:
            from spatial_audio import BackgroundMusic

            if show_opening:
                music = BackgroundMusic(BASE_DIR / "assets/audio/last-delivery.mp3", settings=renderer.audio_settings)
                music.start()
                if not play_opening(renderer, music, cutscene_art):
                    return
            zombie_audio = ZombieAudio(BASE_DIR / "assets/audio", settings=renderer.audio_settings)
        world = DeliveryWorld() if delivery_run else CombatWorld()
        if delivery_run:
            world.select_playable_contract(CONTRACT_NUMBERS[0])
        renderer.combat = world
        if delivery_run:
            if music is not None:
                music.close()
            audio_dir = BASE_DIR / "assets/audio"
            music = BackgroundMusic(audio_dir / "night-delivery-loop.ogg", layers=(
                audio_dir / "night-threat-layer.ogg", audio_dir / "night-chase-layer.ogg",
            ), settings=renderer.audio_settings)
            renderer.delivery = world
            renderer.choosing_delivery = True
            renderer.player_visual.display_scale = DELIVERY_CHARACTER_SCALE
            renderer.combat_visual.display_scale = DELIVERY_CHARACTER_SCALE
            renderer.player_visual.load_delivery_sprites()
            renderer.combat_visual.load_empty_hands()
            renderer.load_neighborhood()
        player, walls = world.player, world.walls
        pressed = set()
        # Modal transitions clear gameplay inputs, but a held key must still be released.
        physical_keys = set()
        target = world.pickup if delivery_run else (world.zombie.x, world.zombie.y)
        aim_player(player, *target)
        cursor = current_cursor()
        mouse_held = False
        suppress_dispatch_repeats = False
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
            sequence_skip_requested = False
            note_close_requested = False
            waypoint_actions = []
            abandon_requested = False
            abandon_decision = None
            pause_requested = False
            pause_keys = []
            discard_actions = False
            bridge = world.bridge_puzzle if delivery_run else None
            circuit_keys = []
            for event in poll_events():
                if event.type == p.SDL_QUIT:
                    running = False
                    continue
                if (event.type == p.SDL_WINDOWEVENT
                        and event.window.event == p.SDL_WINDOWEVENT_FOCUS_LOST):
                    pressed.clear()
                    physical_keys.clear()
                    mouse_held = False
                    if renderer.choosing_delivery:
                        cursor = None
                    lost_focus = True
                    discard_actions = True
                    continue
                if event.type == p.SDL_WINDOWEVENT and event.window.event == p.SDL_WINDOWEVENT_LEAVE:
                    cursor = None
                    continue
                if (event.type == p.SDL_WINDOWEVENT
                        and event.window.event in (p.SDL_WINDOWEVENT_SIZE_CHANGED, p.SDL_WINDOWEVENT_DISPLAY_CHANGED)):
                    cursor = current_cursor()
                    continue
                if event.type == p.SDL_KEYUP:
                    key = event.key.keysym.sym
                    physical_keys.discard(key)
                    pressed.discard(key)
                    continue
                if event.type == p.SDL_MOUSEBUTTONUP and event.button.button == p.SDL_BUTTON_LEFT:
                    mouse_held = False
                    continue
                key = None
                if event.type == p.SDL_KEYDOWN:
                    key = event.key.keysym.sym
                    if event.key.repeat or key in physical_keys:
                        continue
                    physical_keys.add(key)
                if discard_actions:
                    continue
                if renderer.bridge_note_open:
                    if key in (p.SDLK_e, p.SDLK_ESCAPE):
                        note_close_requested = True
                elif bridge is not None and bridge.panel_open:
                    if key is not None:
                        circuit_keys.append(key)
                elif renderer.abandon_confirmation or abandon_requested:
                    if (renderer.abandon_confirmation and abandon_decision is None
                            and key in (p.SDLK_RETURN, p.SDLK_KP_ENTER, p.SDLK_ESCAPE)):
                        abandon_decision = key != p.SDLK_ESCAPE
                elif renderer.pause_page is not None:
                    if key is not None:
                        pause_keys.append(key)
                elif renderer.choosing_delivery:
                    wants_dispatch = key in (p.SDLK_RETURN, p.SDLK_KP_ENTER)
                    if key == p.SDLK_ESCAPE:
                        running = False
                    elif NUMBER_KEYS.get(key) in PLAYABLE_CONTRACTS:
                        preview_choice = CONTRACT_NUMBERS.index(NUMBER_KEYS[key])
                    elif event.type == p.SDL_MOUSEMOTION:
                        cursor = display.cursor_in_canvas(event.motion.x, event.motion.y)
                    elif event.type == p.SDL_MOUSEBUTTONDOWN and event.button.button == p.SDL_BUTTON_LEFT:
                        cursor = display.cursor_in_canvas(event.button.x, event.button.y)
                        if cursor is None:
                            continue
                        if not mouse_held and event.button.clicks <= 1:
                            index = renderer.contract_card_at(*cursor)
                            if index is None:
                                wants_dispatch = renderer.contract_dispatch_at(*cursor)
                            else:
                                preview_choice = index
                        mouse_held = True
                    if wants_dispatch:
                        contract_choice = preview_choice
                        discard_actions = True
                elif key is not None:
                    if key == p.SDLK_ESCAPE:
                        if renderer.map_open or (delivery_run and world.result == "playing" and map_toggle):
                            map_toggle = renderer.map_open
                        elif delivery_run and world.result == "playing":
                            pause_requested = True
                        else:
                            running = False
                        discard_actions = True
                        continue
                    if (delivery_run and world.route_sequence_active
                            and key in (p.SDLK_RETURN, p.SDLK_KP_ENTER)):
                        sequence_skip_requested = True
                        discard_actions = True
                        continue
                    if key == p.SDLK_e:
                        pending_interact = True
                    elif delivery_run and key == p.SDLK_f:
                        pending_bottle_pickup = True
                    elif delivery_run and key == p.SDLK_q:
                        pending_bottle_throw = True
                    elif key == p.SDLK_m:
                        map_toggle = not map_toggle
                    elif (key == p.SDLK_SPACE and delivery_run and world.result == "playing"
                          and renderer.map_open != map_toggle):
                        waypoint_actions.append(("skip", None))
                    elif (key == p.SDLK_TAB and delivery_run and world.result == "playing"
                          and renderer.map_open != map_toggle):
                        waypoint_actions.append(("view", None))
                    elif (delivery_run and world.result != "playing"
                          and key in (p.SDLK_RETURN, p.SDLK_KP_ENTER)):
                        retry_requested = True
                    pressed.add(key)
                    if key == p.SDLK_r:
                        if delivery_run and world.result == "playing":
                            abandon_requested = True
                        else:
                            reset_requested = True
                elif event.type == p.SDL_MOUSEMOTION:
                    cursor = display.cursor_in_canvas(event.motion.x, event.motion.y)
                elif event.type == p.SDL_MOUSEBUTTONDOWN:
                    cursor = display.cursor_in_canvas(event.button.x, event.button.y)
                    if cursor is None:
                        continue
                    button = event.button.button
                    if button == p.SDL_BUTTON_LEFT and suppress_dispatch_repeats:
                        # SDL can deliver the next click of a double-click after departure.
                        if event.button.clicks > 1:
                            continue
                        suppress_dispatch_repeats = False
                    if (delivery_run and world.result == "playing"
                            and renderer.map_open != map_toggle):
                        if button == p.SDL_BUTTON_LEFT:
                            if renderer.map_view_button_at(*cursor):
                                waypoint_actions.append(("view", None))
                            else:
                                waypoint_actions.append(("add", cursor))
                        elif button == p.SDL_BUTTON_RIGHT:
                            waypoint_actions.append(("remove", None))
                    elif button == p.SDL_BUTTON_LEFT:
                        if not mouse_held:
                            pending_click = True
                        mouse_held = True
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
                reset_requested = False
                retry_requested = False
            else:
                renderer.delivery_preview = preview_choice
            pause_changed = False
            if focused and not lost_focus:
                if pause_requested:
                    renderer.pause_page = "main"
                    renderer.pause_index = 0
                    pressed.clear()
                    mouse_held = False
                    pause_changed = True
                for key in pause_keys:
                    previous_page = renderer.pause_page
                    action = renderer.handle_pause_key(key)
                    if action == "quit":
                        return
                    if action == "abandon":
                        abandon_requested = True
                        break
                    if action == "scale":
                        display.set_integer_scale(not display.integer_scale_enabled())
                        cursor = current_cursor()
                    if renderer.pause_page != previous_page:
                        if renderer.pause_page is None:
                            cursor = current_cursor()
                        pause_changed = True
                        break
            motor_sound = None
            if focused and not lost_focus and bridge is not None and bridge.panel_open:
                for key in circuit_keys:
                    if key == p.SDLK_ESCAPE:
                        world.close_bridge_panel()
                        break
                    index = NUMBER_KEYS.get(key, 0) - 1
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
                    world.select_playable_contract(CONTRACT_NUMBERS[contract_choice])
                    renderer.load_neighborhood_ground()
                    if music is not None:
                        music.start()
                else:
                    world.reset()
                if music is not None:
                    music.reset()
                renderer.choosing_delivery = delivery_run and reset_requested
                if delivery_run:
                    delivery_audio.reset()
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
                if contract_choice is None:
                    mouse_held = False
                suppress_dispatch_repeats = contract_choice is not None
                cursor = current_cursor()
                renderer.light = None
                renderer.map_open = False
                renderer.map_full_view = False
                renderer.bridge_note_open = False
                renderer.pause_page = None
                renderer.update_shake(math.inf)
                renderer.update_sprint_pulse(math.inf)
                renderer.update_bottle_pulse(math.inf)
                renderer.update_vehicle_alarm(math.inf)
                target = world.pickup if delivery_run else (world.zombie.x, world.zombie.y)
                aim_player(player, *target)
            elif map_toggle and focused and not lost_focus and delivery_run and world.result == "playing":
                renderer.map_open = not renderer.map_open
                map_toggled = True
                pressed.clear()
                pending_click = pending_interact = mouse_held = False
                pending_bottle_pickup = pending_bottle_throw = False
            if focused and not lost_focus and not reset_requested:
                for action, map_cursor in waypoint_actions:
                    if action == "skip":
                        world.skip_waypoint()
                    elif action == "remove":
                        world.remove_last_waypoint()
                    elif action == "view":
                        renderer.toggle_map_view()
                    elif (point := renderer.map_world_at(*map_cursor)) is not None:
                        world.add_waypoint(point)
            if renderer.choosing_delivery:
                renderer.cursor = cursor if focused and not lost_focus else None
                if music is not None:
                    music.update(dt, focused=False)
                if zombie_audio is not None:
                    zombie_audio.update(dt, distance=None, stride=0.0, active=False)
                with display.frame():
                    renderer.draw(player, walls, target, focused)
                continue
            was_playing = world.result == "playing"
            active = (focused and not lost_focus and not renderer.map_open
                      and not renderer.abandon_confirmation and not confirmation_changed and not renderer.bridge_note_open
                      and renderer.pause_page is None and not pause_changed
                      and (bridge is None or not bridge.panel_open)
                      and contract_choice is None and not retry_requested)
            truck_cue = None
            truck_audio_active = False
            if delivery_run and world.route_sequence_active:
                if active:
                    if sequence_skip_requested:
                        phase_changed = world.skip_route_sequence()
                    else:
                        starting_arrival = world.mission_phase == "arriving" and world.phase_elapsed == 0.0
                        phase_changed = world.advance_route_sequence(dt)
                        truck_audio_active = True
                        if phase_changed and world.result == "playing":
                            truck_cue = world.mission_phase
                        elif starting_arrival and world.phase_elapsed > 0.0:
                            truck_cue = "arriving"
                    if phase_changed:
                        renderer.reset_streetlights()
                        renderer.light = None
                        pressed.clear()
                        mouse_held = False
                active = False
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
            swing_started = False
            if pending_click and active:
                facing = select_facing(player.aim_angle, facing_hint)
                swing_started = world.start_attack(
                    facing=facing, stationary_front_right=True, stationary_swing=delivery_run,
                )
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
            gate_sound = shutter_sound = bus_sound = None
            parcel_picked_up = parcel_dropped = False
            if delivery_run:
                gate_was_closed = world.gate is not None
                front_gate_was_closed = world.front_gate is not None
                shutter_was_closed = world.shutter_closed
                was_waiting = world.parcel == "waiting"
                stops_before = len(world.completed_stops)
                completed = world.update_interaction(
                    dt if active else 0.0, held=active and p.SDLK_e in pressed,
                    pressed=active and pending_interact, moving=player.moved, damaged=player_hit,
                )
                if completed and world.mission_phase == "boarding":
                    pressed.clear()
                    mouse_held = False
                    active = False
                    truck_audio_active = True
                    truck_cue = "boarding"
                if completed and bridge is not None and bridge.panel_open:
                    pressed.clear()
                    mouse_held = False
                gate_opened = completed and gate_was_closed and world.gate is None
                front_gate_opened = completed and front_gate_was_closed and world.front_gate is None
                shutter_closed = completed and not shutter_was_closed and world.shutter_closed
                bus_sound = world.bus_broadcast_source if completed else None
                parcel_picked_up = completed and was_waiting and world.parcel == "carrying"
                parcel_dropped = (completed and len(world.completed_stops) > stops_before
                                  and world.result == "playing")
                if gate_opened or front_gate_opened:
                    gate_sound = world.gate_position if gate_opened else world.front_gate_position
                if shutter_closed:
                    shutter_sound = world.shutter_position
                if gate_sound is not None or shutter_sound is not None:
                    renderer.reset_streetlights()
                    renderer.light = None
            ending = delivery_run and was_playing and world.result in ("delivered", "defeated")
            truck_success = ending and world.result == "delivered" and world.contract.truck_position is not None
            audio_active = active and not reset_requested
            hearing_active = audio_active and world.result == "playing"
            renderer.update_sprint_pulse(dt if hearing_active else math.inf,
                                         world.sprint_step if hearing_active else None)
            vehicle_alarm = world.vehicle_alarm if delivery_run and hearing_active else None
            vehicle_hit = world.vehicle_hit if delivery_run and hearing_active else None
            renderer.update_vehicle_alarm(dt if hearing_active else math.inf, vehicle_alarm)
            swing_sound_due = swing_started
            if strike is not None and strike.uses_stationary_swing:
                # Use the combat clock so pausing or resetting cannot leave a queued sound.
                cue_time = STATIONARY_SWING_SOUND_DELAY - 1e-9
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
            listener = (player.x, player.y)
            enemy_audio = []
            listening_at_corner = (delivery_run and hearing_active
                                   and math.dist(listener, REAR_ALLEY_LISTEN_POINT) <= REAR_ALLEY_LISTEN_RADIUS)
            for zombie, (x, y) in zip(world.zombies, zombie_origins):
                zombie_dx, zombie_dy = zombie.x - x, zombie.y - y
                renderer.combat_visual.update_zombie(zombie, zombie_dx, zombie_dy, paused=not active)
                if not zombie.alive or (delivery_run and not hearing_active):
                    continue
                source = (zombie.x, zombie.y)
                enemy_distance, enemy_pan = sound_position(listener, source)
                if delivery_run and enemy_distance >= ZOMBIE_HEARING_DISTANCE:
                    continue
                recoil_x, recoil_y = zombie.recoil_offset
                enemy_stride = math.hypot(zombie_dx - recoil_x, zombie_dy - recoil_y)
                occluded = hearing_active and any(wall_blocks(listener, source, wall) for wall in walls)
                kind = "regular"
                if zombie.appearance == HEAVY_ZOMBIE_APPEARANCE:
                    kind = "heavy"
                elif listening_at_corner and zombie.state == "patrol" and zombie.patrol_points:
                    kind = "patrol"
                enemy_audio.append(EnemyAcoustics(id(zombie), zombie.state, enemy_distance, enemy_stride,
                                                 enemy_pan, occluded, kind))
            nearest = min(enemy_audio, key=lambda enemy: enemy.distance, default=None)
            distance = nearest.distance if nearest is not None else None
            if music is not None:
                if delivery_run:
                    relief = (world.mission_phase in ("boarding", "departing")
                              or (truck_success and truck_audio_active))
                    impact = 1.0 if player_hit else .8 if strike_landed else .32 if swing_started else 0.0
                    threat, combat = delivery_audio.update(dt, enemy_audio, impact=impact) if hearing_active else (0.0, 0.0)
                    music.update(dt, threat=threat, combat=combat, relief=relief,
                                 focused=hearing_active or (relief and truck_audio_active))
                else:
                    music.update(dt, distance=distance, focused=active)
            if zombie_audio is not None and not ending:
                preserve_map_cue = (renderer.map_open or renderer.bridge_note_open) and focused and not lost_focus
                footsteps = None
                if delivery_run:
                    footsteps = tuple(
                        ZombieFootstep(enemy.source_id, enemy.distance, enemy.stride, enemy.pan, enemy.occluded, enemy.kind)
                        for enemy in select_footstep_sources(enemy_audio)
                    )
                zombie_audio.update(dt, distance=distance if hearing_active else None, active=audio_active,
                                    stride=nearest.stride if nearest is not None else 0.0,
                                    occluded=nearest is not None and nearest.occluded, preserve_map_cue=preserve_map_cue,
                                    preserve_truck_cues=truck_audio_active,
                                    pan=nearest.pan if hearing_active and nearest is not None else 0.0,
                                    footstep_sources=footsteps,
                                    heavy_groan=nearest is not None and nearest.kind == "heavy")
                if truck_cue is not None:
                    x, y, width, depth = world.truck_footprint
                    sound_distance, sound_pan = sound_position(listener, (x + width / 2, y + depth / 2))
                    # The approaching engine remains faintly audible while the truck is off-screen.
                    zombie_audio.play_truck_cue(truck_cue, min(sound_distance, 380), pan=sound_pan)
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
                if gate_sound is not None:
                    sound_distance, sound_pan = sound_position(listener, gate_sound)
                    zombie_audio.play_gate_open(sound_distance, pan=sound_pan)
                if shutter_sound is not None:
                    sound_distance, sound_pan = sound_position(listener, shutter_sound)
                    zombie_audio.play_shutter_close(sound_distance, pan=sound_pan)
                if bus_sound is not None:
                    sound_distance, sound_pan = sound_position(listener, bus_sound)
                    zombie_audio.play_bus_broadcast(sound_distance, pan=sound_pan)
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
            if truck_success:
                if zombie_audio is not None:
                    zombie_audio.stop()
                    if focused and not lost_focus:
                        zombie_audio.play_delivery_cue()
            elif ending:
                if not play_ending(renderer, cutscene_art, world, zombie_audio, player_hit=player_hit, target=target):
                    return
                pressed.clear()
                physical_keys.clear()
                mouse_held = False
                cursor = current_cursor()
                renderer.cursor = cursor
                if world.result == "defeated":
                    renderer.update_shake(math.inf)
                focused = bool(p.SDL_GetWindowFlags(p.window) & p.SDL_WINDOW_INPUT_FOCUS)
                previous = time.perf_counter()
            with display.frame():
                renderer.draw(player, walls, target, focused)
                if smoke_test:
                    output = BASE_DIR.parent / "output/review/R2-C8" / f"ui-{name}.png"
                    capture(output)
                    print(f"R2-C8 SDL capture: {output}", flush=True)
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
                        display.close()
                        p.close_canvas()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dead Route alley delivery game")
    parser.add_argument("--smoke-test", action="store_true",
                        help="render three native SDL fixtures, save PNGs and exit")
    parser.add_argument("--windowed", action="store_true", help="start in a window")
    parser.add_argument("--integer-scale", action="store_true", help="use integer pixel scaling")
    args = parser.parse_args()
    run(args.smoke_test, show_opening=not args.smoke_test, windowed=args.windowed, integer_scale=args.integer_scale)
