"""Dead Route R2-ZA: courier combat and telegraphed eight-direction zombie attacks."""
from __future__ import annotations

import argparse
import ctypes
import math
from pathlib import Path
import time

import pico2d.pico2d as p

from core import WORLD_WIDTH, WORLD_HEIGHT, aim_player
from combat import CombatWorld, MAX_STAMINA
from combat_visual import CombatVisual
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


def world_to_screen(x, y):
    return GROUND_X + x, GROUND_Y + GROUND_SCALE_Y * y


def screen_to_world(x, y):
    return x - GROUND_X, (y - GROUND_Y) / GROUND_SCALE_Y


def sdl_to_world(x, y):
    return screen_to_world(x, WINDOW_HEIGHT - 1 - y)


def current_cursor():
    mouse_window = p.SDL_GetMouseFocus()
    if not mouse_window or p.SDL_GetWindowID(mouse_window) != p.SDL_GetWindowID(p.window):
        return None
    x, y = ctypes.c_int(), ctypes.c_int()
    p.SDL_GetMouseState(ctypes.byref(x), ctypes.byref(y))
    return x.value, y.value


def sorted_drawables(player, walls, zombie=None, *, prop=None):
    # Stable ties: the prop precedes walls and characters at the same ground y.
    objects = [("prop", prop)] if prop is not None else []
    objects.extend(("wall", wall) for wall in walls)
    if zombie is not None:
        objects.append(("zombie", zombie))
    objects.append(("player", player))
    return sorted(objects, key=lambda item: -(item[1][1] if item[0] == "prop" else item[1].y))


def mouse_target(world, visual, mouse_x, mouse_y, light=None):
    position = (world.zombie.x, world.zombie.y)
    if light is None or light.contains(position):
        foot = world_to_screen(*position)
        if visual.zombie_contains(world.zombie, *foot, mouse_x, WINDOW_HEIGHT - 1 - mouse_y):
            return position
    return sdl_to_world(mouse_x, mouse_y)


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
        self.cursor = None
        self.light = None
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
        sx, sy = world_to_screen(x, y)
        dx, dy = self.shake_offset
        return sx + dx, sy + dy

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

    def draw(self, player, walls, target, focused=True):
        p.SDL_SetRenderDrawColor(p.renderer, 0, 0, 0, 255)
        p.SDL_RenderClear(p.renderer)
        origin = (player.x, player.y)
        aim = sdl_to_world(*self.cursor) if self.cursor is not None else target
        dx, dy = aim[0] - origin[0], aim[1] - origin[1]
        self.light = Flashlight(origin, math.atan2(dy, dx) if dx or dy else player.aim_angle, walls)
        outline = self.light.outline()
        self.draw_beam(outline)
        self.draw_sprint_pulse()
        foot = self.project(*origin)
        combat = getattr(self, "combat", None)
        attack = combat.attack if combat is not None else None
        for kind, actor in sorted_drawables(player, walls, combat.zombie if combat else None,
                                            prop=TRASH_CAN_POSITION):
            if kind == "prop":
                if self.light.contains(actor):
                    x, y = self.project(*actor)
                    self.trash_can.draw(x, y + self.trash_can.h, self.trash_can.w * 2, self.trash_can.h * 2)
            elif kind == "wall":
                self.wall(actor, outline)
            elif kind == "zombie":
                if not self.light.contains((actor.x, actor.y)):
                    continue
                x, y = self.project(actor.x, actor.y)
                self.combat_visual.draw_zombie(actor, x, y)
                if combat.result == "playing" and actor.alive and actor.state in ZOMBIE_MARKS:
                    symbol, color = ZOMBIE_MARKS[actor.state]
                    rectangle(x + 24, y + 96, 18, 18, (16, 24, 28))
                    self.font.draw(x + 28, y + 105, symbol, color)
                if (attack is not None and attack.facing == "front_right" and attack.landed
                        and attack.elapsed < attack.hit_time + HIT_MARK_DURATION):
                    x, y = x - 12, y + 83
                    p.draw_line(x - 9, y + 4, x - 3, y + 1, *WHITE)
                    p.draw_line(x - 2, y + 9, x, y + 3, *ORANGE)
                    p.draw_line(x + 4, y + 2, x + 9, y + 4, *WHITE)
            else:
                if combat is None or not self.combat_visual.draw_attack(
                        combat.attack, *foot, walk_frame_index=self.player_visual.frame_index):
                    self.player_visual.draw(*foot)
                cross(*foot, TEAL, size=4)
        # The cursor stays at its screen position while the world shakes.
        target_screen = (world_to_screen(*target) if self.cursor is None
                         else (self.cursor[0], WINDOW_HEIGHT - 1 - self.cursor[1]))
        cross(*target_screen, ORANGE, size=7)
        angle = attack.angle if attack is not None else player.aim_angle
        desired = math.atan2(target[1] - player.y, target[0] - player.x)
        if abs(math.remainder(desired - angle, math.tau)) > math.radians(5):
            tip = self.project(player.x + 27 * math.cos(angle), player.y + 27 * math.sin(angle))
            p.draw_line(*foot, *tip, *TEAL)
            cross(*tip, TEAL, size=2)
        self.font.draw(24, 683, "Dead Route - R4  |  마우스 손전등", WHITE)
        self.font.draw(24, 651, "WASD 이동 · Shift 달리기 · 마우스 조준 · 좌클릭 공격 · R 재시작 · Esc 종료", WHITE)
        if combat is not None:
            self.font.draw(24, 620, f"HP {combat.player_hp}/3", WHITE)
            self.font.draw(24, 592, "스태미나", WHITE)
            rectangle(116, 585, 100, 10, (48, 63, 71))
            stamina_width = round(100 * combat.stamina / MAX_STAMINA)
            if stamina_width:
                rectangle(116, 585, stamina_width, 10, TEAL)
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


def run(smoke_test=False, *, show_opening=False):
    renderer = None
    music = None
    zombie_audio = None
    try:
        p.open_canvas(WINDOW_WIDTH, WINDOW_HEIGHT, sync=True)
        if not p.renderer:
            p.renderer = p.SDL_CreateRenderer(p.window, -1, p.SDL_RENDERER_SOFTWARE)
        if not p.renderer:
            raise RuntimeError(f"SDL renderer initialization failed: {p.SDL_GetError()!r}")
        p.hide_lattice()
        p.SDL_SetWindowTitle(p.window, b"Dead Route - R2-ZA")
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
        world = CombatWorld()
        renderer.combat = world
        player, walls = world.player, world.walls
        pressed = set()
        target = (world.zombie.x, world.zombie.y)
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
            reset_requested = False
            lost_focus = False
            for event in poll_events():
                if event.type == p.SDL_QUIT:
                    running = False
                elif event.type == p.SDL_KEYDOWN and not event.key.repeat:
                    key = event.key.keysym.sym
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
                    mouse_held = False
                    lost_focus = True
            if not running:
                break
            focused = bool(p.SDL_GetWindowFlags(p.window) & p.SDL_WINDOW_INPUT_FOCUS)
            if not focused:
                pressed.clear()
                pending_click = False
                mouse_held = False
            if reset_requested:
                world.reset()
                player, walls = world.player, world.walls
                renderer.player_visual.locomotion = Locomotion()
                renderer.combat_visual.reset_zombie_animation()
                pressed.clear()
                pending_click = False
                mouse_held = False
                cursor = current_cursor()
                renderer.light = None
                target = (world.zombie.x, world.zombie.y)
                aim_player(player, *target)
            renderer.cursor = cursor
            if cursor is not None:
                light = renderer.light or Flashlight((player.x, player.y), player.aim_angle, walls)
                target = mouse_target(world, renderer.combat_visual, *cursor, light)
            active = focused and not lost_focus
            axis_x = int(p.SDLK_d in pressed) - int(p.SDLK_a in pressed)
            axis_y = int(p.SDLK_w in pressed) - int(p.SDLK_s in pressed)
            motion = renderer.player_visual.locomotion
            facing_hint = motion.facing if motion._initialized else None
            if pending_click and active:
                facing = select_facing(player.aim_angle, facing_hint)
                world.start_attack(facing=facing, stationary_front_right=True)
            before = (player.x, player.y)
            zombie_before = (world.zombie.x, world.zombie.y)
            strike = world.attack
            was_landed = strike is not None and strike.landed
            hp_before = world.player_hp
            sprint = p.SDLK_LSHIFT in pressed or p.SDLK_RSHIFT in pressed
            world.update(dt if active else 0.0, axis_x, axis_y, facing_hint=facing_hint, sprint=sprint)
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
            zombie = world.zombie
            distance = math.hypot(zombie.x - player.x, zombie.y - player.y) if zombie.alive else None
            zombie_dx, zombie_dy = zombie.x - zombie_before[0], zombie.y - zombie_before[1]
            if music is not None:
                music.update(dt, distance=distance, focused=active)
            if zombie_audio is not None:
                recoil_x, recoil_y = zombie.recoil_offset
                zombie_audio.update(dt, distance=distance,
                                    stride=math.hypot(zombie_dx - recoil_x, zombie_dy - recoil_y),
                                    active=active and not reset_requested and world.result == "playing")
            dx, dy = player.x - before[0], player.y - before[1]
            renderer.combat_visual.update_zombie(zombie, zombie_dx, zombie_dy, paused=not active)
            if smoke_test:
                name, player.x, player.y = smoke_poses[frame]
            if active and strike is None and world.result == "playing":
                aim_player(player, *target, max_turn=TURN_SPEED * dt)
            display_angle = world.attack.angle if world.attack is not None else player.aim_angle
            renderer.player_visual.update(display_angle, dx, dy)
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
    parser = argparse.ArgumentParser(description="Dead Route R2-C8 eight-direction combat sample")
    parser.add_argument("--smoke-test", action="store_true",
                        help="render three native SDL fixtures, save PNGs and exit")
    args = parser.parse_args()
    run(args.smoke_test, show_opening=not args.smoke_test)
