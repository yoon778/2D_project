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
from delivery import ALLEY_PROP, DeliveryWorld
from flashlight import Flashlight, RANGE as LIGHT_RANGE
from locomotion import Locomotion, select_facing
from player_visual import PlayerVisual
from spatial_audio import ZombieAudio
import opening

WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
GROUND_X = 160.0
GROUND_Y = 90.0
GROUND_SCALE_Y = 0.60
WALL_HEIGHT = 110
DELIVERY_CHARACTER_SCALE = 0.75
BASE_DIR = Path(__file__).resolve().parent
TRASH_CAN_PATH = BASE_DIR / "assets/props/alley-trash-can.png"
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


def sorted_drawables(player, walls, zombie=None, *, zombies=(), prop=None, station=None):
    # Stable ties: fixed props precede walls and characters at the same ground y.
    objects = [("prop", prop)] if prop is not None else []
    if station is not None:
        objects.append(("station", station))
    objects.extend(("wall", wall) for wall in walls)
    if zombie is not None:
        objects.append(("zombie", zombie))
    objects.extend(("zombie", enemy) for enemy in zombies)
    objects.append(("player", player))
    return sorted(objects, key=lambda item: -(item[1][1] if item[0] in ("prop", "station") else item[1].y))


def lit_zombie_columns(light, zombie, screen_origin_x):
    return tuple((math.ceil(left + screen_origin_x - 0.5), math.ceil(right + screen_origin_x - 0.5))
                 for left, right in light.spans_at(zombie.y))


def mouse_target(world, visual, mouse_x, mouse_y, light=None, camera=(0.0, 0.0), shake=(0, 0)):
    screen_y = WINDOW_HEIGHT - 1 - mouse_y
    for zombie in sorted(world.zombies, key=lambda enemy: enemy.y):
        position = (zombie.x, zombie.y)
        x, y = world_to_screen(*position, camera)
        if not visual.zombie_contains(zombie, x + shake[0], y + shake[1], mouse_x, screen_y):
            continue
        if light is not None and not any(left <= mouse_x < right for left, right in
                                         lit_zombie_columns(light, zombie, x - zombie.x + shake[0])):
            continue
        # A wall drawn in front can cover the upper part of a lit sprite.
        wx, wy = mouse_x - shake[0], screen_y - shake[1]
        for wall in world.walls:
            left, bottom = world_to_screen(wall.x, wall.y, camera)
            if (wall.y < zombie.y and left <= wx < left + wall.width
                    and bottom <= wy < bottom + WALL_HEIGHT + wall.depth * GROUND_SCALE_Y):
                break
        else:
            return position
    return sdl_to_world(mouse_x, mouse_y, camera)


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
        self.combat = None
        self.delivery = None
        self.cursor = None
        self.light = None
        self.camera = (0.0, 0.0)
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

    def close(self):
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

    def draw_map(self, player):
        world = self.delivery
        width, height = world.world_size
        scale = min(860 / width, 500 / height)
        left, bottom = (WINDOW_WIDTH - width * scale) / 2, 108
        p.SDL_SetRenderDrawColor(p.renderer, 14, 20, 23, 255)
        p.SDL_RenderClear(p.renderer)
        rectangle(left, bottom, width * scale, height * scale, (46, 55, 57))
        rectangle(left, bottom, width * scale, height * scale, (99, 118, 118), filled=False)
        for wall in world.walls:
            rectangle(left + wall.x * scale, bottom + wall.y * scale,
                      wall.width * scale, wall.depth * scale, (18, 27, 30))
            rectangle(left + wall.x * scale, bottom + wall.y * scale,
                      wall.width * scale, wall.depth * scale, (75, 94, 94), filled=False)
        for (x, y), color in ((world.pickup, ORANGE), (world.destination, TEAL)):
            rectangle(left + x * scale - 4, bottom + y * scale - 4, 8, 8, color)
        x, y = left + player.x * scale, bottom + player.y * scale
        cross(x, y, WHITE, size=7)
        p.draw_line(x, y, x + 16 * math.cos(player.aim_angle), y + 16 * math.sin(player.aim_angle), *WHITE)
        self.font.draw(left, 652, "배달 구역 지도", WHITE)
        north = left + width * scale - 12
        self.font.draw(north - 22, 630, "N", WHITE)
        p.draw_line(north, 623, north, 638, *WHITE)
        p.draw_line(north - 4, 633, north, 638, *WHITE)
        p.draw_line(north + 4, 633, north, 638, *WHITE)
        self.font.draw(left, 75, "+ 현재 위치", WHITE)
        for offset, label, color in ((155, "수령지", ORANGE), (290, "배송지", TEAL)):
            rectangle(left + offset, 72, 8, 8, color)
            self.font.draw(left + offset + 16, 75, label, color)
        self.font.draw(left, 40, "M 닫기 · 지도 확인 중 일시정지", WHITE)

    def draw_beam(self, outline):
        points = [self.light.origin] + [point for point, _ in outline]
        vertices = (p.SDL_Vertex * len(points))()
        for i, point in enumerate(points):
            x, y = self.project(*point)
            strength = 1.0 - math.dist(self.light.origin, point) / LIGHT_RANGE
            color = p.SDL_Color(round(28 + 104 * strength), round(26 + 84 * strength),
                                round(23 + 53 * strength), 255)
            vertices[i] = p.SDL_Vertex(p.SDL_FPoint(x, WINDOW_HEIGHT - 1 - y), color)
        indices = [index for i in range(1, len(vertices) - 1) for index in (0, i, i + 1)]
        triangles = (ctypes.c_int * len(indices))(*indices)
        if p.SDL_RenderGeometry(p.renderer, None, vertices, len(vertices), triangles, len(indices)) != 0:
            raise RuntimeError(f"Flashlight geometry failed: {p.SDL_GetError()!r}")

    def wall(self, wall, outline):
        x, y = self.project(wall.x, wall.y)
        rectangle(x, y, wall.width, WALL_HEIGHT, (12, 14, 18))
        rectangle(x, y + WALL_HEIGHT, wall.width,
                  wall.depth * GROUND_SCALE_Y, (16, 18, 22))
        for (a, first), (b, last) in zip(outline, outline[1:]):
            if first is wall and last is wall and abs(a[1] - wall.y) < 1e-7 and abs(b[1] - wall.y) < 1e-7:
                start, end = sorted((self.project(*a)[0], self.project(*b)[0]))
                rectangle(start, y, end - start, WALL_HEIGHT, (53, 47, 40))
        rectangle(x, y, wall.width, WALL_HEIGHT, (27, 30, 36), filled=False)
        rectangle(x, y + WALL_HEIGHT, wall.width,
                  wall.depth * GROUND_SCALE_Y, (27, 30, 36), filled=False)

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

    def draw_station(self, position, pickup):
        x, y = self.project(*position)
        if pickup:
            rectangle(x - 14, y, 28, 23, (138, 86, 47))
            rectangle(x - 14, y + 23, 28, 8, (186, 132, 76))
            rectangle(x - 3, y + 11, 6, 20, (226, 185, 106))
            label = "수령"
        else:
            rectangle(x - 17, y, 34, 43, (37, 100, 96))
            rectangle(x - 17, y + 43, 34, 5, (86, 155, 145))
            rectangle(x - 11, y + 25, 22, 5, (11, 29, 34))
            label = "배달"
        rectangle(x + 19, y + 26, 50, 23, (16, 24, 28))
        self.font.draw(x + 26, y + 37, label, ORANGE if pickup else TEAL)

    def draw_delivery_hud(self):
        delivery = self.delivery
        status, guide = {
            "waiting": ("미수령 · 0/1", "남서쪽 거점에서 택배 수령"),
            "carrying": ("소지 중 · 0/1", "북동쪽 골목의 배송함 찾기"),
            "delivered": ("전달 완료 · 1/1", ""),
        }[delivery.parcel]
        self.font.draw(24, 564, f"택배 {status}", WHITE)
        if delivery.result != "playing":
            success = delivery.result == "delivered"
            title = "배달 성공" if success else "배달 실패 · 체력 소진"
            rectangle(425, 303, 430, 112, (17, 25, 31))
            rectangle(425, 303, 430, 112, TEAL if success else ORANGE, filled=False)
            self.font.draw(455, 382, title, TEAL if success else ORANGE)
            self.font.draw(455, 335, "R 다시 시작 · Esc 종료", WHITE)
        elif delivery.can_interact() and self.light.contains(delivery.next_stop):
            action = "택배 수령" if delivery.parcel == "waiting" else "택배 전달"
            self.font.draw(520, 56, f"E  {action}", TEAL)
        else:
            self.font.draw(24, 538, guide, WHITE)

    def draw_lit_zombie(self, zombie, combat, attack):
        x, y = self.project(zombie.x, zombie.y)
        columns = lit_zombie_columns(self.light, zombie, x - zombie.x)
        if not columns:
            return
        left, _, width, _ = self.combat_visual.zombie_rect(zombie, x, y)
        if not any(start < left + width and end > left for start, end in columns):
            return
        # Keep the projection and pixel sampling of the original sprite.
        try:
            for start, end in columns:
                start, end = max(0, start), min(WINDOW_WIDTH, end)
                if start >= end or start >= left + width or end <= left:
                    continue
                clip = p.SDL_Rect(start, 0, end - start, WINDOW_HEIGHT)
                p.SDL_RenderSetClipRect(p.renderer, ctypes.byref(clip))
                self.combat_visual.draw_zombie(zombie, x, y)
                if start <= x < end:
                    self.draw_zombie_markers(zombie, combat, attack, x, y)
        finally:
            p.SDL_RenderSetClipRect(p.renderer, None)

    def draw_zombie_markers(self, zombie, combat, attack, x, y):
        scale = self.combat_visual.display_scale
        if combat.result == "playing" and zombie.alive and zombie.state in ZOMBIE_MARKS:
            symbol, color = ZOMBIE_MARKS[zombie.state]
            rectangle(x + 24 * scale, y + 96 * scale, 18, 18, (16, 24, 28))
            self.font.draw(x + 24 * scale + 4, y + 96 * scale + 9, symbol, color)
        if (attack is not None and attack.facing == "front_right" and attack.hit_target is zombie
                and attack.elapsed < attack.hit_time + HIT_MARK_DURATION):
            x, y = x - 12 * scale, y + 83 * scale
            p.draw_line(x - 9, y + 4, x - 3, y + 1, *WHITE)
            p.draw_line(x - 2, y + 9, x, y + 3, *ORANGE)
            p.draw_line(x + 4, y + 4, x + 9, y + 2, *WHITE)

    def draw(self, player, walls, target, focused=True):
        if self.map_open:
            self.draw_map(player)
            return
        p.SDL_SetRenderDrawColor(p.renderer, 0, 0, 0, 255)
        p.SDL_RenderClear(p.renderer)
        origin = (player.x, player.y)
        aim = sdl_to_world(*self.cursor, self.camera) if self.cursor is not None else target
        dx, dy = aim[0] - origin[0], aim[1] - origin[1]
        world_size = self.combat.world_size if self.combat is not None else (WORLD_WIDTH, WORLD_HEIGHT)
        self.light = Flashlight(origin, math.atan2(dy, dx) if dx or dy else player.aim_angle, walls, world_size)
        outline = self.light.outline()
        self.draw_beam(outline)
        self.draw_sprint_pulse()
        foot = self.project(*origin)
        combat = getattr(self, "combat", None)
        attack = combat.attack if combat is not None else None
        delivery = self.delivery
        courier_style = {"empty_handed": delivery.parcel != "carrying"} if delivery is not None else {}
        for kind, actor in sorted_drawables(player, walls, zombies=combat.zombies if combat else (),
                                            prop=ALLEY_PROP if delivery is not None else TRASH_CAN_POSITION,
                                            station=delivery.next_stop if delivery is not None else None):
            if kind == "prop":
                if self.light.contains(actor):
                    x, y = self.project(*actor)
                    self.trash_can.draw(x, y + self.trash_can.h, self.trash_can.w * 2, self.trash_can.h * 2)
            elif kind == "station":
                if self.light.contains(actor):
                    self.draw_station(actor, delivery.parcel == "waiting")
            elif kind == "wall":
                self.wall(actor, outline)
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
            controls += " · E 수령/전달 · M 지도"
        self.font.draw(24, 683, title, WHITE)
        self.font.draw(24, 651, controls + " · R 재시작 · Esc 종료", WHITE)
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
            renderer.player_visual.display_scale = DELIVERY_CHARACTER_SCALE
            renderer.combat_visual.display_scale = DELIVERY_CHARACTER_SCALE
            renderer.player_visual.load_delivery_sprites()
            renderer.combat_visual.load_empty_hands()
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
            reset_requested = False
            lost_focus = False
            map_toggle = False
            for event in poll_events():
                if event.type == p.SDL_QUIT:
                    running = False
                elif event.type == p.SDL_KEYDOWN and not event.key.repeat:
                    key = event.key.keysym.sym
                    if key == p.SDLK_e and key not in pressed:
                        pending_interact = True
                    elif key == p.SDLK_m and key not in pressed:
                        map_toggle = not map_toggle
                    pressed.add(key)
                    if key == p.SDLK_ESCAPE:
                        running = False
                    elif key == p.SDLK_r:
                        reset_requested = True
                elif event.type == p.SDL_KEYUP and not event.key.repeat:
                    pressed.discard(event.key.keysym.sym)
                elif event.type == p.SDL_MOUSEMOTION:
                    cursor = (event.motion.x, event.motion.y)
                elif event.type == p.SDL_MOUSEBUTTONDOWN and event.button.button == p.SDL_BUTTON_LEFT:
                    cursor = (event.button.x, event.button.y)
                    if not mouse_held:
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
            if reset_requested:
                world.reset()
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
                target = world.pickup if delivery_run else (world.zombie.x, world.zombie.y)
                aim_player(player, *target)
            elif map_toggle and focused and not lost_focus and delivery_run and world.result == "playing":
                renderer.map_open = not renderer.map_open
                pressed.clear()
                pending_click = pending_interact = mouse_held = False
            renderer.follow(player)
            renderer.cursor = cursor
            if cursor is not None:
                light = renderer.light or Flashlight((player.x, player.y), player.aim_angle, walls, world.world_size)
                target = mouse_target(world, renderer.combat_visual, *cursor, light, renderer.camera, renderer.shake_offset)
            active = focused and not lost_focus and not renderer.map_open
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
